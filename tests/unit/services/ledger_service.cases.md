# Test cases — `app/services/ledger_service.py`

> **Spec:** `tests/unit/services/ledger_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — spec fill-gaps G1, G2. G1: new rules `get_project_component_ledger` R1a and `get_project_component_total_cost` R1a [BUG-1278, BUG-1954] → new LSV-PCL-10, LSV-PCT-07 (strict xfail). G2: exact lock clauses (`reconcile_machine_item` R9, `reconcile_inventory` R7) → LSV-RMI-13 and LSV-RINV-15 now pin `FOR UPDATE OF machine_items` / `FOR UPDATE OF inventory` and cite the new rule numbers. Both earlier gaps closed. No ID retired.
> **Revision:** 3 (2026-11-22) — from `ledger_service.verify.md`: finding 1 (mutant L230 `hasattr(..., 'value')`) → LSV-GIB-01 Then 4 and LSV-GIB-04 Then 4 check `type(result["inventory_type"]) is str` (GIB-01 lines 4–5 renumbered 5–6); finding 2 (mutants L340/L341, default `skip`/`limit`) → new LSV-TBU-04 (patched manager, call kwargs); finding 3 (TC6 on the allowed path) → new LSV-PCL-11. No ID retired.
> **Counts:** 106 cases · 82 expected-to-pass · 24 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `get_machine_ledger` 11 (2 bug) · `get_machine_balance` 8 (3 bug) · `reconcile_machine_item` 14 (3 bug) · `get_project_component_ledger` 11 (1 bug) · `get_project_component_total_cost` 7 (1 bug) · `get_inventory_ledger` 9 · `get_inventory_balance` 9 (3 bug) · `reconcile_inventory` 18 (6 bug) · `get_attachment_ledger` 9 · `get_item_movement_summary` 6 (3 bug) · `get_transactions_by_user` 4 (2 bug).
- **Depth:** full (skill step 1a): the two reconciles write stock rows and the balances answer money. The pass-through reads get one real-data card per argument (dropping or swapping any argument changes the result), one default-limit card, one workspace card and one TC6 card each. Manager rules are not re-tested (see `ledger_manager.cases.md`); each manager bug reached gets one pass-through card, strict.
- **Notable design choices:**
  - **Commit proof.** Reconcile paths that write nothing (balanced, error, other status) prove the commit with an unrelated **extra row X** flushed after the commit point: it survives a test-level rollback only if the service committed. Error cards prove the rollback by X being gone.
  - **TC3 after the manager wrote.** RMI-10 / RINV-12 wrap the real manager method so it flushes the adjustment and then raises; this is the only way to show the rollback discards the manager's own writes (every real manager error comes before its writes, or is a bug path).
  - **Patched manager** for the message mapping where real rows cannot reach the branch today: an `error` dict without `error` key, an unknown status, `adjusted` with `discrepancy 0` (BUG-3042, only producible after BUG-653), inventory error/adjusted with history (BUG-655 crashes today), a plain-string `inventory_type`.
  - **BUG-3043** is split: `total_value == Decimal(...)` holds today (an exact binary float compares equal) → pass cards; `isinstance(..., Decimal)` and `str(...) == "1234.50"` → strict xfail.
  - **Locks (BUG-643/644)** are checked on the recorded SQL only: the snapshot SELECT's lock clause is exactly `FOR UPDATE OF machine_items` / `FOR UPDATE OF inventory` (spec G2: the lookup outer-joins `items`). The race and "held until commit" are deferred to integration.
  - **Projects (revisit after launch):** today's behaviour, real access check, no patch. The only project bug cards are the deleted-project 404 (BUG-1278, PCL-10 / PCT-07), which the spec now tags (G1); BUG-647, BUG-654 stay deferred.
  - The bug path of BUG-645 / BUG-650 / BUG-655 (an exception passed on) gets no passing card; TC6 of `get_transactions_by_user` uses a patched manager instead.
- **Needs a decision:** None (gaps 1 and 2 closed by spec G1, G2).

## Conventions for this module

**IDs.** `LSV` = ledger_service. `GML` get_machine_ledger · `GMB` get_machine_balance · `RMI` reconcile_machine_item · `PCL` get_project_component_ledger · `PCT` get_project_component_total_cost · `GIL` get_inventory_ledger · `GIB` get_inventory_balance · `RINV` reconcile_inventory · `GAL` get_attachment_ledger · `IMS` get_item_movement_summary · `TBU` get_transactions_by_user.

**Actors and fixed values.**
- `svc` = `ledger_service` (`from app.services.ledger_service import LedgerService, ledger_service`). `db` first, every other argument by keyword. `result` = the return value; for reconciles `result, messages = ...`.
- W0, W1, W2 = three workspaces, built in that order (`W0.id < W1.id < W2.id`); W1 is the request's workspace, `W1.owner_user_id = U1.id`. U1, U2, U3 = profiles: U1, U2 active members of W1 (U1 role `"owner"`, U2 role `"ground-team"`); U3 an active member of W1 with role `"ground-team"`; U9 a profile that is a member of W2 only. `current_user` = U2 (the profile object). U1 created every Given row.
- I1 = item "Bolt", I2 = item "Nut" (W1); I0 (W0), I9 (W2) = items there. M1, M2 = machines of W1; M0 (W0), M9 (W2). F1, F2 = factories of W1; F0 (W0), F9 (W2). A1, A2 = attachments of W1; A0 (W0), A9 (W2).
- MISSING = `999999999`. `T(d)` = 2025-06-d 10:00:00 (aware UTC if the column is tz-aware, naive otherwise; dates passed as arguments use the same form). Every Given entry has an explicit `performed_at`.
- `MessageType` (`app.schemas.response`); a message check reads `m.type.value`, `m.message`, `m.details`. Timestamps are not compared.

**Given rows** (add + flush, in the order written; ids rise in that order within one table). After "but" a card lists the columns that differ.
- **mentry** = machine item ledger row: `workspace_id W1.id, machine_id M1.id, item_id I1.id, transaction_type "consumption", quantity 1, qty_before 0, qty_after 1, unit_cost 2.00, total_cost 2.00, value_before 0.00, value_after 2.00, avg_price_before 2.00, avg_price_after 2.00, performed_by U1.id, performed_at T(1)`; other NOT NULL columns any valid value.
- **ientry** = inventory ledger row: `workspace_id W1.id, inventory_type InventoryTypeEnum.STORAGE, factory_id F1.id, item_id I1.id, transaction_type "transfer_in", quantity 1, qty_before 0, qty_after 1, unit_cost 2.00, total_cost 2.00, avg_price_before 2.00, avg_price_after 2.00, performed_by U1.id, performed_at T(1)`.
- **pentry** = project component item ledger row: `workspace_id W1.id, project_component_id C1.id, item_id I1.id, transaction_type "transfer_in", quantity 1, total_cost 10.00, performed_by U1.id, performed_at T(1)`.
- **aentry** = attachment ledger row: `workspace_id W1.id, attachment_id A1.id, entity_type "machine", transaction_type "ready", file_name "a.pdf", mime_type "application/pdf", file_size 10, performed_by U1.id, performed_at T(1)`.
- **msnap** = `machine_items` row `workspace_id W1.id, machine_id M1.id, item_id I1.id, qty 10`. **isnap** = live `inventory` row `workspace_id W1.id, factory_id F1.id, item_id I1.id, inventory_type STORAGE, qty 4, avg_price 0.00, created_by U1.id, updated_by U1.id, is_deleted False`.
- Projects: PA = project of W1 (factory F1, `visibility "workspace"`, created_by U1); PP = PA but `visibility "invited_only"` (U3 is not a project member); PD = PA but `is_deleted True`, `deleted_at T(1)`, `deleted_by U1.id`. C1, C2 = components of PA; CP = component of PP; CD = component of PD; C0 = component of a W0 project; C9 = component of a W2 project.
- **commit point** = `db.commit()` after the last Given line; a line marked "(after the commit point)" runs after it.
- **extra X** (after the commit point) = `X = Department(workspace_id=W2.id, name="Extra", created_by=U1.id)`, add, flush. **pending Q** (after the commit point) = `Q = Department(workspace_id=W2.id, name="Pending", created_by=U1.id)`, add, not flushed. **edit E(r)** (after the commit point) = `r.notes = "Edited"`, not flushed.

**Named checks.**
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- `committed:` lines: before the first one the test runs `db.rollback()` once, then each line uses a fresh query.
- `session:` "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **recorder** = `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` with `rec` appending the statement text, attached just before the When and removed after. "The <table> SELECT" = recorded SELECTs whose FROM names that table (at least one). "ORDER BY is `performed_at DESC, id DESC`" ignores case, whitespace and table qualifiers.
- `returns ids` = `[r.id for r in <list>]` compared with `==` to the list given.

**Mocks.** No external is mocked (`utcnow` of messages is not compared). **Patched manager** = `patch.object(svc.ledger_manager, "<method>", return_value=R)`. **Writes then raises** = `real = svc.ledger_manager.<method>` taken before patching, `ERR = RuntimeError("after write")`, `patch.object(svc.ledger_manager, "<method>", side_effect=f)` where `f(*a, **k)` calls `real(*a, **k)` then raises ERR.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-NNN")`; write the call as shown, also when a parameter does not exist yet.

**Race simulations.** None.

## `LedgerService.get_machine_ledger`

### LSV-GML-01 — with no optional argument every entry of the machine comes back newest first
- **Rules:** get_machine_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = mentry, but `transaction_type "transfer_in"`, `performed_at T(1)`.
2. E2 = mentry, but `performed_at T(2)`.
3. E3 = mentry, but `item_id I2.id`, `performed_at T(3)`.
4. E4 = mentry, but `machine_id M2.id`, `performed_at T(4)`.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns ids: `[E3.id, E2.id, E1.id]`.

### LSV-GML-02 — the workspace reaches the manager
- **Rules:** get_machine_ledger R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = mentry, but `performed_at T(1)`.
2. E2 = mentry, but `performed_at T(2)`.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### LSV-GML-03 — item_id reaches the manager
- **Rules:** get_machine_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = mentry, but `performed_at T(1)`.
2. E2 = mentry, but `item_id I2.id`, `performed_at T(2)`.
3. E3 = mentry, but `performed_at T(3)`.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id, item_id=I1.id)`.

**Then**
1. returns ids: `[E3.id, E1.id]`.

### LSV-GML-04 — transaction_type reaches the manager
- **Rules:** get_machine_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = mentry, but `transaction_type "transfer_in"`, `performed_at T(1)`.
2. E2 = mentry, but `performed_at T(2)`.
3. E3 = mentry, but `item_id I2.id`, `performed_at T(3)`.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id, transaction_type="consumption")`.

**Then**
1. returns ids: `[E3.id, E2.id]`.

### LSV-GML-05 — a full date range reaches the manager
- **Rules:** get_machine_ledger R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = mentry, but `performed_at T(1)`.
2. E2 = mentry, but `performed_at T(2)`.
3. E3 = mentry, but `performed_at T(3)`.
4. E4 = mentry, but `performed_at T(4)`.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id, start_date=T(2), end_date=T(3))`.

**Then**
1. returns ids: `[E3.id, E2.id]`.

### LSV-GML-06 — skip and limit reach the manager in their places
- **Rules:** get_machine_ledger R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, k = 1 … 5: Ek = mentry, but `performed_at T(k)`.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns ids: `[E4.id, E3.id]`.

### LSV-GML-07 — the default limit is 100
- **Rules:** get_machine_ledger R1 (defaults)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, k = 0 … 100: Qk = mentry, but `performed_at datetime(2025, 6, 1) + timedelta(minutes=k)` (same tz form as T).

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `Q0.id not in [r.id for r in result]`.
3. returns: `result[0].id == Q100.id`.

### LSV-GML-08 — a database error from the manager passes on with no commit and no rollback
- **Rules:** get_machine_ledger R2; TC6
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. E1 = mentry.
2. (after the commit point) `sp = db.begin_nested()`, then pending Q.

**When**
- `svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id, limit=-1)` inside `with pytest.raises(DataError) as exc:` inside spies.

**Then**
1. raises: `isinstance(exc.value, DataError)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: after `sp.rollback()`, usable.

### LSV-GML-09 — the read neither commits nor rolls back
- **Rules:** get_machine_ledger R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = mentry, but `performed_at T(1)`.
2. E2 = mentry, but `performed_at T(2)`.
3. pending Q.
4. edit E(E2).

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id)`, inside spies.

**Then**
1. returns: `len(result) == 2`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `E2 in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. committed: `departments` rows with `name == "Pending"`: exactly 0.

### LSV-GML-10 — pass-through BUG-640: the list is ordered by performed_at then id
- **Rules:** get_machine_ledger R1 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 2 (ORDER BY is `performed_at DESC` only)

**Given**
1. E1 = mentry, but `performed_at T(5)`.
2. E2 = mentry, but `performed_at T(5)`.
3. recorder attached.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. the `machine_item_ledger` SELECT: ORDER BY is `performed_at DESC, id DESC`.

### LSV-GML-11 — pass-through BUG-341: a date range and a type combine
- **Rules:** get_machine_ledger R1 [BUG-341]
- **Kind:** bug
- **Expect:** xfail BUG-341
- **Fails today on:** Then 1 (the type is ignored when a date range is given: E2 is returned too)

**Given**
1. E1 = mentry, but `performed_at T(10)`.
2. E2 = mentry, but `transaction_type "transfer_in"`, `performed_at T(11)`.
3. E3 = mentry, but `performed_at T(25)`.

**When**
- `result = svc.get_machine_ledger(db, machine_id=M1.id, workspace_id=W1.id, start_date=T(5), end_date=T(20), transaction_type="consumption")`.

**Then**
1. returns ids: `[E1.id]`.

## `LedgerService.get_machine_balance`

### LSV-GMB-01 — a bucket with history: ids echoed, latest quantity and value
- **Rules:** get_machine_balance R1, R2 (value part that holds today), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = mentry, but `qty_after 5`, `value_after 12.50`, `performed_at T(3)`.
2. E2 = mentry, but `qty_after 40`, `value_after 1234.50`, `performed_at T(9)`.

**When**
- `result = svc.get_machine_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `set(result.keys()) == {"machine_id", "item_id", "quantity", "total_value"}`.
2. returns: `result["machine_id"] == M1.id`, `result["item_id"] == I1.id`.
3. returns: `result["quantity"] == 40`, `isinstance(result["quantity"], int)`.
4. returns: `result["total_value"] == Decimal("1234.50")`.

### LSV-GMB-02 — BUG-3043: the value of a bucket with history is the exact Decimal
- **Rules:** get_machine_balance R2 [BUG-3043]
- **Kind:** bug
- **Expect:** xfail BUG-3043
- **Fails today on:** Then 2 (a `float` 1234.5 is returned)

**Given**
1. E1 = mentry, but `qty_after 40`, `value_after 1234.50`, `performed_at T(9)`.

**When**
- `result = svc.get_machine_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 40`.
2. returns: `isinstance(result["total_value"], Decimal)`.
3. returns: `str(result["total_value"]) == "1234.50"`.

### LSV-GMB-03 — an empty bucket gives quantity 0 and value 0
- **Rules:** get_machine_balance R1, R2 (value part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = mentry, but `item_id I2.id`, `qty_after 7`.

**When**
- `result = svc.get_machine_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["machine_id"] == M1.id`, `result["item_id"] == I1.id`.
2. returns: `result["quantity"] == 0`.
3. returns: `result["total_value"] == Decimal("0.00")`.

### LSV-GMB-04 — BUG-3043: an empty bucket's value is Decimal("0.00")
- **Rules:** get_machine_balance R2 [BUG-3043]
- **Kind:** bug
- **Expect:** xfail BUG-3043
- **Fails today on:** Then 2 (a `float` 0.0 is returned)

**Given**
1. No machine ledger rows.

**When**
- `result = svc.get_machine_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 0`.
2. returns: `isinstance(result["total_value"], Decimal)`.
3. returns: `str(result["total_value"]) == "0.00"`.

### LSV-GMB-05 — a W2 machine's bucket is not visible from W1
- **Rules:** get_machine_balance R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E9 = mentry, but `workspace_id W2.id`, `machine_id M9.id`, `item_id I9.id`, `qty_after 30`, `value_after 60.00`.

**When**
- `result = svc.get_machine_balance(db, machine_id=M9.id, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["machine_id"] == M9.id`, `result["item_id"] == I9.id`.
2. returns: `result["quantity"] == 0`.
3. returns: `result["total_value"] == Decimal("0.00")`.

### LSV-GMB-06 — a W0 machine's bucket is not visible from W1
- **Rules:** get_machine_balance R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E0 = mentry, but `workspace_id W0.id`, `machine_id M0.id`, `item_id I0.id`, `qty_after 30`, `value_after 60.00`.

**When**
- `result = svc.get_machine_balance(db, machine_id=M0.id, item_id=I0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 0`.
2. returns: `result["total_value"] == Decimal("0.00")`.

### LSV-GMB-07 — the balance read neither commits nor rolls back
- **Rules:** get_machine_balance R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = mentry, but `qty_after 3`.
2. pending Q.
3. edit E(E1).

**When**
- `result = svc.get_machine_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`, inside spies.

**Then**
1. returns: `result["quantity"] == 3`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `E1 in db.dirty`.
6. session: `len(db.dirty) == 1`.

### LSV-GMB-08 — pass-through BUG-641: the latest entry breaks ties by id
- **Rules:** get_machine_balance R1 [BUG-641]
- **Kind:** bug
- **Expect:** xfail BUG-641
- **Fails today on:** Then 2 (ORDER BY is `performed_at DESC` only)

**Given**
1. E1 = mentry, but `qty_after 10`, `value_after 10.00`, `performed_at T(10)`.
2. E2 = mentry, but `qty_after 20`, `value_after 40.00`, `performed_at T(10)`.
3. recorder attached.

**When**
- `result = svc.get_machine_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["machine_id"] == M1.id`.
2. the `machine_item_ledger` SELECT: ORDER BY is `performed_at DESC, id DESC`, followed by `LIMIT`.
3. returns: `result["quantity"] == 20`.

## `LedgerService.reconcile_machine_item`

RM rows used below: **RE1** = mentry, but `qty_after 10`, `avg_price_after 2.00`, `value_after 20.00`, `performed_at T(1)`; **RE2** = mentry, but `qty_after 15`, `avg_price_after 2.50`, `value_after 37.50`, `performed_at T(2)` (ledger quantity 15).

### LSV-RMI-01 — balanced: one success message, committed, nothing written
- **Rules:** reconcile_machine_item R1, R2, R6; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. RE1. 2. RE2.
3. S = msnap, but `qty 15`.
4. extra X.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result == {"status": "balanced", "ledger_qty": 15, "snapshot_qty": 15, "discrepancy": 0, "adjustment_created": False}`.
2. returns: `len(messages) == 1`.
3. returns: `messages[0].type.value == "success"`, `messages[0].message == "Machine inventory is balanced at 15 units."`, `messages[0].details is None`.
4. committed: `departments` rows with `name == "Extra"`: exactly 1.
5. committed: machine ledger rows of M1/I1: exactly 2.
6. committed: re-read S: `qty == 15`.
7. committed: `machine_activity_events` rows of M1: exactly 0.

### LSV-RMI-02 — adjusted: a warning with the result, then a success message
- **Rules:** reconcile_machine_item R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. RE1. 2. RE2.
3. S = msnap (qty 10).

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result == {"status": "adjusted", "ledger_qty": 15, "snapshot_qty": 10, "discrepancy": 5, "adjustment_created": True}`.
2. returns: `len(messages) == 2`.
3. returns: `messages[0].type.value == "warning"`, `messages[0].message == "Discrepancy found and corrected: 5 units adjusted."`.
4. returns: `messages[0].details == result`.
5. returns: `messages[1].type.value == "success"`, `messages[1].message == "Snapshot updated to match ledger."`, `messages[1].details is None`.

### LSV-RMI-03 — adjusted: the snapshot, the adjustment row and the event are committed as the current user
- **Rules:** reconcile_machine_item R1, R6; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. RE1. 2. RE2.
3. S = msnap (qty 10).

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["status"] == "adjusted"`.
2. committed: re-read S: `qty == 15`.
3. committed: machine ledger rows of M1/I1: exactly 3.
4. committed: the one with `transaction_type == "inventory_adjustment"`: `source_type == "reconciliation"`, `performed_by == U2.id`, `qty_after == 15`.
5. committed: `machine_activity_events` rows of M1: exactly 1.
6. committed: that event: `event_type == "ledger_reconciled"`, `performed_by == U2.id`, `description == "Ledger reconciled for Bolt: snapshot 10 → 15"`.

### LSV-RMI-04 — a negative discrepancy is reported as its absolute value
- **Rules:** reconcile_machine_item R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RE1 (ledger quantity 10, no RE2).
2. S = msnap, but `qty 15`.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["discrepancy"] == -5`, `result["status"] == "adjusted"`.
2. returns: `len(messages) == 2`.
3. returns: `messages[0].message == "Discrepancy found and corrected: 5 units adjusted."`.

### LSV-RMI-05 — error (snapshot missing, ledger holds stock): one warning, committed, nothing written
- **Rules:** reconcile_machine_item R4
- **Kind:** error
- **Expect:** pass

**Given**
1. RE1. 2. RE2.
3. No `machine_items` row for M1/I1.
4. extra X.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result == {"status": "error", "ledger_qty": 15, "snapshot_qty": 0, "discrepancy": 15, "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions"}`.
2. returns: `len(messages) == 1`.
3. returns: `messages[0].type.value == "warning"`, `messages[0].message == "Reconciliation issue: Snapshot missing for item with ledger transactions"`, `messages[0].details is None`.
4. committed: `departments` rows with `name == "Extra"`: exactly 1.
5. committed: `machine_items` rows of M1/I1: exactly 0.
6. committed: machine ledger rows of M1/I1: exactly 2.

### LSV-RMI-06 — an error result without an error text says "Unknown error"
- **Rules:** reconcile_machine_item R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "error", "ledger_qty": 3, "snapshot_qty": 0, "discrepancy": 3, "adjustment_created": False}`; patched manager `reconcile_machine_item` returns R.
2. extra X.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result is R`.
2. returns: `len(messages) == 1`.
3. returns: `messages[0].type.value == "warning"`, `messages[0].message == "Reconciliation issue: Unknown error"`, `messages[0].details is None`.
4. committed: `departments` rows with `name == "Extra"`: exactly 1.

### LSV-RMI-07 — any other status gives no message and still commits
- **Rules:** reconcile_machine_item R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "pending", "ledger_qty": 3, "snapshot_qty": 3, "discrepancy": 0, "adjustment_created": False}`; patched manager `reconcile_machine_item` returns R.
2. extra X.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result is R`.
2. returns: `messages == []`.
3. committed: `departments` rows with `name == "Extra"`: exactly 1.

### LSV-RMI-08 — an empty bucket with no snapshot: one message, nothing written, committed
- **Rules:** reconcile_machine_item R2, R4 (bug-independent part of BUG-649)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machine ledger rows and no `machine_items` row for M1/I1.
2. extra X.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["ledger_qty"] == 0`, `result["adjustment_created"] is False`.
2. returns: `len(messages) == 1`.
3. committed: `departments` rows with `name == "Extra"`: exactly 1.
4. committed: `machine_items` rows of M1/I1: exactly 0.
5. committed: machine ledger rows of M1/I1: exactly 0.
6. committed: `machine_activity_events` rows of M1: exactly 0.

### LSV-RMI-09 — pass-through BUG-649: an empty bucket is balanced at 0 units
- **Rules:** reconcile_machine_item R2 [BUG-649]
- **Kind:** bug
- **Expect:** xfail BUG-649
- **Fails today on:** Then 2 (a warning "Reconciliation issue: …" is given)

**Given**
1. No machine ledger rows and no `machine_items` row for M1/I1.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `len(messages) == 1`.
2. returns: `messages[0].type.value == "success"`, `messages[0].message == "Machine inventory is balanced at 0 units."`.
3. returns: `result["status"] == "balanced"`.

### LSV-RMI-10 — an exception after the manager wrote: rolled back, same object, nothing saved
- **Rules:** reconcile_machine_item R7; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. RE1. 2. RE2.
3. S = msnap (qty 10).
4. extra X.
5. writes then raises on `reconcile_machine_item`.

**When**
- `svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)` inside `with pytest.raises(RuntimeError) as exc:` inside spies.

**Then**
1. raises: `exc.value is ERR`.
2. mock called: `rb.call_count >= 1`.
3. committed: re-read S: `qty == 10`.
4. committed: machine ledger rows of M1/I1: exactly 2.
5. committed: `machine_activity_events` rows of M1: exactly 0.
6. committed: `departments` rows with `name == "Extra"`: exactly 0.
7. session: usable.

### LSV-RMI-11 — an exception while building the messages rolls back
- **Rules:** reconcile_machine_item R7; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "balanced"}`; patched manager `reconcile_machine_item` returns R.
2. extra X.

**When**
- `svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)` inside `with pytest.raises(KeyError) as exc:` inside spies.

**Then**
1. raises: `exc.value.args == ("ledger_qty",)`.
2. mock called: `rb.call_count >= 1`.
3. mock called: `cm.call_count == 0`.
4. committed: `departments` rows with `name == "Extra"`: exactly 0.

### LSV-RMI-12 — a failing commit is rolled back and re-raised, nothing saved
- **Rules:** reconcile_machine_item R8; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. RE1. 2. RE2.
3. S = msnap (qty 10).

**When**
- `svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`, inside failing commit.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `qty == 10`.
4. count: machine ledger rows of M1/I1: exactly 2.
5. count: `machine_activity_events` rows of M1: exactly 0.

### LSV-RMI-13 — BUG-643: the snapshot is read with FOR UPDATE OF machine_items
- **Rules:** reconcile_machine_item R9 [BUG-643]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-643
- **Fails today on:** Then 2 (the `machine_items` SELECT has no lock clause)

**Given**
1. RE1. 2. RE2.
3. S = msnap (qty 10).
4. recorder attached.

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["status"] == "adjusted"`.
2. the `machine_items` SELECT (its FROM starts with `machine_items`): after collapsing whitespace and ignoring case, its text ends with `FOR UPDATE OF machine_items`.
3. the `machine_items` SELECT: contains neither `SKIP LOCKED` nor `NOWAIT`, and `FOR UPDATE` occurs exactly once (no lock on `items`).

### LSV-RMI-14 — pass-through BUG-650: an empty average price on the latest entry still reconciles
- **Rules:** reconcile_machine_item R1, R3, R6 [BUG-650]
- **Kind:** bug
- **Expect:** xfail BUG-650
- **Fails today on:** Then 1 (the call raises TypeError: the empty price is multiplied)

**Given**
1. RE1.
2. E2 = mentry, but `qty_after 12`, `avg_price_after None`, `performed_at T(2)`.
3. S = msnap (qty 10).

**When**
- `result, messages = svc.reconcile_machine_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["status"] == "adjusted"`, `result["discrepancy"] == 2`.
2. returns: `messages[0].message == "Discrepancy found and corrected: 2 units adjusted."`.
3. committed: re-read S: `qty == 12`.

## `LedgerService.get_project_component_ledger`

*Revisit after launch: today's behaviour only.*

### LSV-PCL-01 — an allowed user gets the component's entries newest first
- **Rules:** get_project_component_ledger R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = pentry, but `performed_at T(1)`.
2. P2 = pentry, but `item_id I2.id`, `performed_at T(3)`.
3. P3 = pentry, but `performed_at T(2)`.
4. P4 = pentry, but `project_component_id C2.id`, `performed_at T(4)`.

**When**
- `result = svc.get_project_component_ledger(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns ids: `[P2.id, P3.id, P1.id]`.

### LSV-PCL-02 — item_id reaches the manager
- **Rules:** get_project_component_ledger R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = pentry, but `performed_at T(1)`.
2. P2 = pentry, but `item_id I2.id`, `performed_at T(3)`.
3. P3 = pentry, but `performed_at T(2)`.

**When**
- `result = svc.get_project_component_ledger(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id, item_id=I1.id)`.

**Then**
1. returns ids: `[P3.id, P1.id]`.

### LSV-PCL-03 — skip and limit reach the manager in their places
- **Rules:** get_project_component_ledger R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 4 rows, k = 1 … 4: Pk = pentry, but `performed_at T(k)`.

**When**
- `result = svc.get_project_component_ledger(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id, skip=1, limit=2)`.

**Then**
1. returns ids: `[P3.id, P2.id]`.

### LSV-PCL-04 — the default limit is 100
- **Rules:** get_project_component_ledger R2 (defaults)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, k = 0 … 100: Pk = pentry, but `performed_at datetime(2025, 6, 1) + timedelta(minutes=k)`.

**When**
- `result = svc.get_project_component_ledger(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `P0.id not in [r.id for r in result]`.

### LSV-PCL-05 — an unknown component: 404, the ledger is not read
- **Rules:** get_project_component_ledger R1, R3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. P1 = pentry.
2. recorder attached.

**When**
- `svc.get_project_component_ledger(db, project_component_id=MISSING, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Project component not found"`.
3. recorder: no recorded statement names `project_component_item_ledger`.

### LSV-PCL-06 — a W2 component: 404
- **Rules:** get_project_component_ledger R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = pentry, but `workspace_id W2.id`, `project_component_id C9.id`, `item_id I9.id`.

**When**
- `svc.get_project_component_ledger(db, project_component_id=C9.id, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Project component not found"`.

### LSV-PCL-07 — a W0 component: 404
- **Rules:** get_project_component_ledger R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = pentry, but `workspace_id W0.id`, `project_component_id C0.id`, `item_id I0.id`.

**When**
- `svc.get_project_component_ledger(db, project_component_id=C0.id, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Project component not found"`.

### LSV-PCL-08 — a private project the user may not open: 403
- **Rules:** get_project_component_ledger R1
- **Kind:** error
- **Expect:** pass

**Given**
1. PE = pentry, but `project_component_id CP.id`.

**When**
- `svc.get_project_component_ledger(db, project_component_id=CP.id, workspace_id=W1.id, user_id=U3.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 403`.
2. raises: `exc.value.detail == "You do not have access to this project"`.

### LSV-PCL-09 — a refusal neither commits nor rolls back
- **Rules:** get_project_component_ledger R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = pentry.
2. pending Q.
3. edit E(P1).

**When**
- `svc.get_project_component_ledger(db, project_component_id=MISSING, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:` inside spies.

**Then**
1. raises: `exc.value.status_code == 404`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `P1 in db.dirty`.

### LSV-PCL-10 — BUG-1278: a component of a deleted project gets the project 404, the ledger is not read
- **Rules:** get_project_component_ledger R1a [BUG-1278, BUG-1954]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Author:** claude
- **Fails today on:** Then 1 (no error is raised: `[]` is returned)

**Given**
1. PE = pentry, but `project_component_id CD.id`.
2. recorder attached.

**When**
- `svc.get_project_component_ledger(db, project_component_id=CD.id, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Project with ID {PD.id} not found"`.
3. recorder: no recorded statement names `project_component_item_ledger`.


### LSV-PCL-11 — an allowed read neither commits nor rolls back
- **Rules:** get_project_component_ledger R2, R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = pentry, but `performed_at T(1)`.
2. P2 = pentry, but `performed_at T(2)`.
3. pending Q.
4. edit E(P1).

**When**
- `result = svc.get_project_component_ledger(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id)`, inside spies.

**Then**
1. returns: `len(result) == 2`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `P1 in db.dirty`.
6. session: `len(db.dirty) == 1`.

## `LedgerService.get_project_component_total_cost`

*Revisit after launch: today's behaviour only (float, no bug).*

### LSV-PCT-01 — an allowed user gets the component's summed cost as a float
- **Rules:** get_project_component_total_cost R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = pentry, but `total_cost 1000.00`.
2. P2 = pentry, but `transaction_type "consumption"`, `total_cost 250.50`.
3. P3 = pentry, but `project_component_id C2.id`, `total_cost 99.00`.

**When**
- `result = svc.get_project_component_total_cost(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `set(result.keys()) == {"project_component_id", "total_cost"}`.
2. returns: `result["project_component_id"] == C1.id`.
3. returns: `result["total_cost"] == 1250.5`, `isinstance(result["total_cost"], float)`.

### LSV-PCT-02 — no rows gives 0.0
- **Rules:** get_project_component_total_cost R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P3 = pentry, but `project_component_id C2.id`, `total_cost 99.00`.

**When**
- `result = svc.get_project_component_total_cost(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result == {"project_component_id": C1.id, "total_cost": 0.0}`.
2. returns: `isinstance(result["total_cost"], float)`.

### LSV-PCT-03 — an unknown component: 404, the cost is not computed
- **Rules:** get_project_component_total_cost R1
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. P1 = pentry.
2. recorder attached.

**When**
- `svc.get_project_component_total_cost(db, project_component_id=MISSING, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Project component not found"`.
3. recorder: no recorded statement names `project_component_item_ledger`.

### LSV-PCT-04 — a W2 component: 404
- **Rules:** get_project_component_total_cost R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = pentry, but `workspace_id W2.id`, `project_component_id C9.id`, `item_id I9.id`.

**When**
- `svc.get_project_component_total_cost(db, project_component_id=C9.id, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Project component not found"`.

### LSV-PCT-05 — a private project the user may not open: 403
- **Rules:** get_project_component_total_cost R1
- **Kind:** error
- **Expect:** pass

**Given**
1. PE = pentry, but `project_component_id CP.id`.

**When**
- `svc.get_project_component_total_cost(db, project_component_id=CP.id, workspace_id=W1.id, user_id=U3.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 403`.
2. raises: `exc.value.detail == "You do not have access to this project"`.

### LSV-PCT-06 — the cost read neither commits nor rolls back
- **Rules:** get_project_component_total_cost R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = pentry.
2. pending Q.
3. edit E(P1).

**When**
- `result = svc.get_project_component_total_cost(db, project_component_id=C1.id, workspace_id=W1.id, user_id=U2.id)`, inside spies.

**Then**
1. returns: `result["project_component_id"] == C1.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `P1 in db.dirty`.

### LSV-PCT-07 — BUG-1278: a component of a deleted project gets the project 404, the cost is not computed
- **Rules:** get_project_component_total_cost R1a [BUG-1278, BUG-1954]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Author:** claude
- **Fails today on:** Then 1 (no error is raised: a dict with `total_cost 0.0` is returned)

**Given**
1. PE = pentry, but `project_component_id CD.id`, `total_cost 40.00`.
2. recorder attached.

**When**
- `svc.get_project_component_total_cost(db, project_component_id=CD.id, workspace_id=W1.id, user_id=U2.id)` inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Project with ID {PD.id} not found"`.
3. recorder: no recorded statement names `project_component_item_ledger`.

## `LedgerService.get_inventory_ledger`

IL rows used below: **G1** = ientry, but `performed_at T(1)`; **G2** = ientry, but `inventory_type DAMAGED`, `transaction_type "damaged"`, `performed_at T(2)`; **G3** = ientry, but `factory_id F2.id`, `performed_at T(3)`; **G4** = ientry, but `item_id I2.id`, `transaction_type "consumption"`, `performed_at T(4)`; **G0** = ientry, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`, `performed_at T(5)`; **G9** = ientry, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`, `performed_at T(6)`.

### LSV-GIL-01 — only the workspace: every W1 entry newest first, W0 and W2 left out
- **Rules:** get_inventory_ledger R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. G0. 2. G1. 3. G2. 4. G3. 5. G4. 6. G9.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns ids: `[G4.id, G3.id, G2.id, G1.id]`.

### LSV-GIL-02 — inventory_type reaches the manager
- **Rules:** get_inventory_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. G1. 2. G2. 3. G3.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id, inventory_type=InventoryTypeEnum.DAMAGED)`.

**Then**
1. returns ids: `[G2.id]`.

### LSV-GIL-03 — factory_id reaches the manager
- **Rules:** get_inventory_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. G1. 2. G3. 3. G4.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns ids: `[G3.id]`.

### LSV-GIL-04 — item_id reaches the manager
- **Rules:** get_inventory_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. G1. 2. G3. 3. G4.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns ids: `[G4.id]`.

### LSV-GIL-05 — transaction_type reaches the manager
- **Rules:** get_inventory_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. G1. 2. G2. 3. G3. 4. G4.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id, transaction_type="transfer_in")`.

**Then**
1. returns ids: `[G3.id, G1.id]`.

### LSV-GIL-06 — a full date range reaches the manager
- **Rules:** get_inventory_ledger R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. G1. 2. G2. 3. G3. 4. G4.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id, start_date=T(2), end_date=T(3))`.

**Then**
1. returns ids: `[G3.id, G2.id]`.

### LSV-GIL-07 — skip and limit reach the manager in their places
- **Rules:** get_inventory_ledger R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. G1. 2. G2. 3. G3. 4. G4.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns ids: `[G3.id, G2.id]`.

### LSV-GIL-08 — the default limit is 100
- **Rules:** get_inventory_ledger R1 (defaults)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, k = 0 … 100: Qk = ientry, but `performed_at datetime(2025, 6, 1) + timedelta(minutes=k)`.

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `Q0.id not in [r.id for r in result]`.

### LSV-GIL-09 — the read neither commits nor rolls back
- **Rules:** get_inventory_ledger R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. G1. 2. G2.
3. pending Q.
4. edit E(G2).

**When**
- `result = svc.get_inventory_ledger(db, workspace_id=W1.id)`, inside spies.

**Then**
1. returns: `len(result) == 2`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `G2 in db.dirty`.
6. session: `len(db.dirty) == 1`.

## `LedgerService.get_inventory_balance`

### LSV-GIB-01 — an empty bucket: ids and the enum value echoed, quantity 0, value 0
- **Rules:** get_inventory_balance R1, R2, R3 (value part that holds today), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No inventory ledger rows.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.DAMAGED, workspace_id=W1.id)`.

**Then**
1. returns: `set(result.keys()) == {"factory_id", "item_id", "inventory_type", "quantity", "total_value"}`.
2. returns: `result["factory_id"] == F1.id`, `result["item_id"] == I1.id`.
3. returns: `result["inventory_type"] == "DAMAGED"`.
4. returns: `type(result["inventory_type"]) is str`.
5. returns: `result["quantity"] == 0`.
6. returns: `result["total_value"] == Decimal("0.00")`.

### LSV-GIB-02 — BUG-3043: an empty bucket's value is Decimal("0.00")
- **Rules:** get_inventory_balance R3 [BUG-3043]
- **Kind:** bug
- **Expect:** xfail BUG-3043
- **Fails today on:** Then 2 (a `float` 0.0 is returned)

**Given**
1. No inventory ledger rows.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 0`.
2. returns: `isinstance(result["total_value"], Decimal)`.
3. returns: `str(result["total_value"]) == "0.00"`.

### LSV-GIB-03 — a value without .value is echoed as given
- **Rules:** get_inventory_balance R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. patched manager `get_inventory_balance` returns `(0, Decimal("0.00"))`.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type="STORAGE", workspace_id=W1.id)`.

**Then**
1. returns: `result["inventory_type"] == "STORAGE"`.
2. returns: `result["quantity"] == 0`.

### LSV-GIB-04 — the manager's quantity and value are shaped into the dict
- **Rules:** get_inventory_balance R1, R3 (value part that holds today)
- **Kind:** happy
- **Expect:** pass
- **Author:** claude

**Given**
1. patched manager `get_inventory_balance` returns `(50, Decimal("1234.50"))`.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 50`.
2. returns: `result["total_value"] == Decimal("1234.50")`.
3. returns: `result["inventory_type"] == "STORAGE"`.
4. returns: `type(result["inventory_type"]) is str`.

### LSV-GIB-05 — BUG-3043: a non-zero value stays the exact Decimal
- **Rules:** get_inventory_balance R3 [BUG-3043]
- **Kind:** bug
- **Expect:** xfail BUG-3043
- **Author:** claude
- **Fails today on:** Then 2 (a `float` 1234.5 is returned)

**Given**
1. patched manager `get_inventory_balance` returns `(50, Decimal("1234.50"))`.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 50`.
2. returns: `isinstance(result["total_value"], Decimal)`.
3. returns: `str(result["total_value"]) == "1234.50"`.

### LSV-GIB-06 — pass-through BUG-655: a bucket with history answers its balance
- **Rules:** get_inventory_balance R1 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: `value_after` is read)

**Given**
1. G1 = ientry, but `qty_after 10`, `avg_price_after 5.00`, `performed_at T(1)`.
2. G2 = ientry, but `qty_after 40`, `avg_price_after 6.50`, `performed_at T(2)`.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 40`.
2. returns: `result["total_value"] == Decimal("260.00")`.

### LSV-GIB-07 — a W2 factory's bucket is not visible from W1
- **Rules:** get_inventory_balance R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. G9 = ientry, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`, `qty_after 30`.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F9.id, item_id=I9.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 0`.
2. returns: `result["total_value"] == Decimal("0.00")`.

### LSV-GIB-08 — a W0 factory's bucket is not visible from W1
- **Rules:** get_inventory_balance R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. G0 = ientry, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`, `qty_after 30`.

**When**
- `result = svc.get_inventory_balance(db, factory_id=F0.id, item_id=I0.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result["quantity"] == 0`.
2. returns: `result["total_value"] == Decimal("0.00")`.

### LSV-GIB-09 — the balance read neither commits nor rolls back
- **Rules:** get_inventory_balance R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. G2 = ientry, but `item_id I2.id`.
2. pending Q.
3. edit E(G2).

**When**
- `result = svc.get_inventory_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id)`, inside spies.

**Then**
1. returns: `result["quantity"] == 0`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `G2 in db.dirty`.
6. session: `len(db.dirty) == 1`.

## `LedgerService.reconcile_inventory`

In this section every call is `svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`, written in full in each card.

### LSV-RINV-01 — balanced: one success message, committed, nothing written
- **Rules:** reconcile_inventory R1, R2, R6; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No inventory ledger rows.
2. S = isnap, but `qty 0`, `avg_price 0.00`.
3. extra X.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result == {"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}`.
2. returns: `len(messages) == 1`.
3. returns: `messages[0].type.value == "success"`, `messages[0].message == "Inventory is balanced at 0 units."`, `messages[0].details is None`.
4. committed: `departments` rows with `name == "Extra"`: exactly 1.
5. committed: inventory ledger rows of W1: exactly 0.
6. committed: re-read S: `qty == 0`, `updated_by == U1.id`.

### LSV-RINV-02 — adjusted: a warning with the result, then a success message
- **Rules:** reconcile_inventory R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No inventory ledger rows.
2. S = isnap (qty 4, avg_price 0.00).

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result == {"status": "adjusted", "ledger_qty": 0, "snapshot_qty": 4, "discrepancy": -4, "adjustment_created": True}`.
2. returns: `len(messages) == 2`.
3. returns: `messages[0].type.value == "warning"`, `messages[0].message == "Discrepancy found and corrected: 4 units adjusted."`.
4. returns: `messages[0].details == result`.
5. returns: `messages[1].type.value == "success"`, `messages[1].message == "Snapshot updated to match ledger."`, `messages[1].details is None`.

### LSV-RINV-03 — adjusted: the snapshot and the adjustment row are committed as the current user, no event
- **Rules:** reconcile_inventory R1, R6; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No inventory ledger rows.
2. S = isnap (qty 4, avg_price 0.00).

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["status"] == "adjusted"`.
2. committed: re-read S: `qty == 0`.
3. committed: inventory ledger rows of W1/F1/I1/STORAGE: exactly 1.
4. committed: that row: `transaction_type == "inventory_adjustment"`, `source_type == "reconciliation"`, `performed_by == U2.id`, `qty_after == 0`.
5. committed: that row: `notes.startswith("Reconciliation adjustment: Snapshot was 4, ledger shows 0. Discrepancy: -4")`.
6. committed: `machine_activity_events` rows: exactly 0.

### LSV-RINV-04 — adjusted with discrepancy 0: two messages, the warning carries the result, committed
- **Rules:** reconcile_inventory R4 (bug-independent part), R6
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "adjusted", "ledger_qty": 10, "snapshot_qty": 10, "discrepancy": 0, "adjustment_created": True}`; patched manager `reconcile_inventory` returns R.
2. extra X.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result is R`.
2. returns: `len(messages) == 2`.
3. returns: `messages[0].type.value == "warning"`, `messages[0].details == R`.
4. returns: `messages[1].type.value == "success"`, `messages[1].message == "Snapshot updated to match ledger."`.
5. committed: `departments` rows with `name == "Extra"`: exactly 1.

### LSV-RINV-05 — BUG-3042: a price-only correction names the average price
- **Rules:** reconcile_inventory R4 [BUG-3042]
- **Kind:** bug
- **Expect:** xfail BUG-3042
- **Author:** claude
- **Fails today on:** Then 2 (the text is "Discrepancy found and corrected: 0 units adjusted.")

**Given**
1. `R = {"status": "adjusted", "ledger_qty": 10, "snapshot_qty": 10, "discrepancy": 0, "adjustment_created": True}`; patched manager `reconcile_inventory` returns R.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `len(messages) == 2`.
2. returns: `messages[0].message == "Discrepancy found and corrected: average price updated to match ledger."`.

### LSV-RINV-06 — a positive non-zero discrepancy keeps the units text
- **Rules:** reconcile_inventory R3
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "adjusted", "ledger_qty": 13, "snapshot_qty": 10, "discrepancy": 3, "adjustment_created": True}`; patched manager `reconcile_inventory` returns R.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result is R`.
2. returns: `len(messages) == 2`.
3. returns: `messages[0].message == "Discrepancy found and corrected: 3 units adjusted."`.

### LSV-RINV-07 — error: one warning with the manager's text, committed
- **Rules:** reconcile_inventory R5
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "error", "ledger_qty": 12, "snapshot_qty": 0, "discrepancy": 12, "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions"}`; patched manager `reconcile_inventory` returns R.
2. extra X.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result is R`.
2. returns: `len(messages) == 1`.
3. returns: `messages[0].type.value == "warning"`, `messages[0].message == "Reconciliation issue: Snapshot missing for item with ledger transactions"`, `messages[0].details is None`.
4. committed: `departments` rows with `name == "Extra"`: exactly 1.

### LSV-RINV-08 — an error result without an error text says "Unknown error"
- **Rules:** reconcile_inventory R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "error", "ledger_qty": 3, "snapshot_qty": 0, "discrepancy": 3, "adjustment_created": False}`; patched manager `reconcile_inventory` returns R.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result is R`.
2. returns: `len(messages) == 1`.
3. returns: `messages[0].message == "Reconciliation issue: Unknown error"`.

### LSV-RINV-09 — any other status gives no message and still commits
- **Rules:** reconcile_inventory R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "pending", "ledger_qty": 3, "snapshot_qty": 3, "discrepancy": 0, "adjustment_created": False}`; patched manager `reconcile_inventory` returns R.
2. extra X.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result is R`.
2. returns: `messages == []`.
3. committed: `departments` rows with `name == "Extra"`: exactly 1.

### LSV-RINV-10 — an empty bucket with no snapshot: one message, nothing written, committed
- **Rules:** reconcile_inventory R2, R5 (bug-independent part of BUG-649)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No inventory ledger rows and no `inventory` row for W1/F1/I1/STORAGE.
2. extra X.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["ledger_qty"] == 0`, `result["adjustment_created"] is False`.
2. returns: `len(messages) == 1`.
3. committed: `departments` rows with `name == "Extra"`: exactly 1.
4. committed: `inventory` rows of W1/F1/I1: exactly 0.
5. committed: inventory ledger rows of W1: exactly 0.

### LSV-RINV-11 — pass-through BUG-649: an empty bucket is balanced at 0 units
- **Rules:** reconcile_inventory R2 [BUG-649]
- **Kind:** bug
- **Expect:** xfail BUG-649
- **Fails today on:** Then 2 (a warning "Reconciliation issue: …" is given)

**Given**
1. No inventory ledger rows and no `inventory` row for W1/F1/I1/STORAGE.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `len(messages) == 1`.
2. returns: `messages[0].type.value == "success"`, `messages[0].message == "Inventory is balanced at 0 units."`.
3. returns: `result["status"] == "balanced"`.

### LSV-RINV-12 — an exception after the manager wrote: rolled back, same object, nothing saved
- **Rules:** reconcile_inventory R6; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. No inventory ledger rows.
2. S = isnap (qty 4, avg_price 0.00).
3. extra X.
4. writes then raises on `reconcile_inventory`.

**When**
- `svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)` inside `with pytest.raises(RuntimeError) as exc:` inside spies.

**Then**
1. raises: `exc.value is ERR`.
2. mock called: `rb.call_count >= 1`.
3. committed: re-read S: `qty == 4`, `updated_by == U1.id`.
4. committed: inventory ledger rows of W1: exactly 0.
5. committed: `departments` rows with `name == "Extra"`: exactly 0.
6. session: usable.

### LSV-RINV-13 — an exception while building the messages rolls back
- **Rules:** reconcile_inventory R6; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"status": "balanced"}`; patched manager `reconcile_inventory` returns R.
2. extra X.

**When**
- `svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)` inside `with pytest.raises(KeyError) as exc:` inside spies.

**Then**
1. raises: `exc.value.args == ("ledger_qty",)`.
2. mock called: `rb.call_count >= 1`.
3. mock called: `cm.call_count == 0`.
4. committed: `departments` rows with `name == "Extra"`: exactly 0.

### LSV-RINV-14 — a failing commit is rolled back and re-raised, nothing saved
- **Rules:** reconcile_inventory R6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No inventory ledger rows.
2. S = isnap (qty 4, avg_price 0.00).

**When**
- `svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`, inside failing commit.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `qty == 4`.
4. count: inventory ledger rows of W1: exactly 0.

### LSV-RINV-15 — BUG-644: the snapshot is read with FOR UPDATE OF inventory
- **Rules:** reconcile_inventory R7 [BUG-644]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-644
- **Fails today on:** Then 2 (the `inventory` SELECT has no lock clause)

**Given**
1. No inventory ledger rows.
2. S = isnap (qty 4, avg_price 0.00).
3. recorder attached.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["status"] == "adjusted"`.
2. the `inventory` SELECT (its FROM starts with the table `inventory`, not `inventory_ledger`): after collapsing whitespace and ignoring case, its text ends with `FOR UPDATE OF inventory`.
3. that SELECT: contains neither `SKIP LOCKED` nor `NOWAIT`, and `FOR UPDATE` occurs exactly once (no lock on `items`).

### LSV-RINV-16 — pass-through BUG-655: a bucket with history reconciles and commits
- **Rules:** reconcile_inventory R1, R3, R6 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: `value_after` is read)

**Given**
1. G1 = ientry, but `qty_after 12`, `avg_price_after 6.50`, `performed_at T(1)`.
2. S = isnap, but `qty 10`, `avg_price 6.50`.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result == {"status": "adjusted", "ledger_qty": 12, "snapshot_qty": 10, "discrepancy": 2, "adjustment_created": True}`.
2. returns: `messages[0].message == "Discrepancy found and corrected: 2 units adjusted."`.
3. committed: re-read S: `qty == 12`.

### LSV-RINV-17 — pass-through BUG-653: a wrong price alone is corrected and named
- **Rules:** reconcile_inventory R4 [BUG-653, BUG-3042]
- **Kind:** bug
- **Expect:** xfail BUG-653
- **Fails today on:** Then 1 (the result is `balanced`, the price is left)

**Given**
1. No inventory ledger rows.
2. S = isnap, but `qty 0`, `avg_price 5.00`.

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["status"] == "adjusted"`, `result["discrepancy"] == 0`.
2. returns: `messages[0].message == "Discrepancy found and corrected: average price updated to match ledger."`.
3. committed: re-read S: `avg_price == Decimal("0.00")`.

### LSV-RINV-18 — pass-through BUG-652: the committed snapshot names the reconciling user
- **Rules:** reconcile_inventory R1, R6 [BUG-652]
- **Kind:** bug
- **Expect:** xfail BUG-652
- **Fails today on:** Then 2 (`updated_by` stays U1)

**Given**
1. No inventory ledger rows.
2. S = isnap (qty 4, avg_price 0.00, updated_by U1).

**When**
- `result, messages = svc.reconcile_inventory(db, factory_id=F1.id, item_id=I1.id, inventory_type=InventoryTypeEnum.STORAGE, workspace_id=W1.id, current_user=U2)`.

**Then**
1. returns: `result["status"] == "adjusted"`.
2. committed: re-read S: `updated_by == U2.id`.

## `LedgerService.get_attachment_ledger`

AL rows used below: **L1** = aentry, but `performed_at T(1)`; **L2** = aentry, but `entity_type "project"`, `transaction_type "deleted"`, `performed_at T(2)`; **L3** = aentry, but `attachment_id A2.id`, `transaction_type "deleted"`, `performed_at T(3)`; **L0** = aentry, but `workspace_id W0.id`, `attachment_id A0.id`, `performed_at T(4)`; **L9** = aentry, but `workspace_id W2.id`, `attachment_id A9.id`, `performed_at T(5)`.

### LSV-GAL-01 — only the workspace: every W1 entry newest first, W0 and W2 left out
- **Rules:** get_attachment_ledger R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L0. 2. L1. 3. L2. 4. L3. 5. L9.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns ids: `[L3.id, L2.id, L1.id]`.

### LSV-GAL-02 — attachment_id reaches the manager
- **Rules:** get_attachment_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1. 2. L2. 3. L3.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id, attachment_id=A1.id)`.

**Then**
1. returns ids: `[L2.id, L1.id]`.

### LSV-GAL-03 — entity_type reaches the manager
- **Rules:** get_attachment_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1. 2. L2. 3. L3.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id, entity_type="machine")`.

**Then**
1. returns ids: `[L3.id, L1.id]`.

### LSV-GAL-04 — transaction_type reaches the manager
- **Rules:** get_attachment_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1. 2. L2. 3. L3.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id, transaction_type="deleted")`.

**Then**
1. returns ids: `[L3.id, L2.id]`.

### LSV-GAL-05 — start_date alone reaches the manager
- **Rules:** get_attachment_ledger R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1. 2. L2. 3. L3.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id, start_date=T(2))`.

**Then**
1. returns ids: `[L3.id, L2.id]`.

### LSV-GAL-06 — end_date alone reaches the manager
- **Rules:** get_attachment_ledger R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1. 2. L2. 3. L3.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id, end_date=T(2))`.

**Then**
1. returns ids: `[L2.id, L1.id]`.

### LSV-GAL-07 — skip and limit reach the manager in their places
- **Rules:** get_attachment_ledger R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1. 2. L2. 3. L3.
4. L4 = aentry, but `performed_at T(4)`.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns ids: `[L3.id, L2.id]`.

### LSV-GAL-08 — the default limit is 100
- **Rules:** get_attachment_ledger R1 (defaults)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, k = 0 … 100: Qk = aentry, but `performed_at datetime(2025, 6, 1) + timedelta(minutes=k)`.

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `Q0.id not in [r.id for r in result]`.

### LSV-GAL-09 — the read neither commits nor rolls back
- **Rules:** get_attachment_ledger R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. L1. 2. L2.
3. pending Q.
4. edit E(L2).

**When**
- `result = svc.get_attachment_ledger(db, workspace_id=W1.id)`, inside spies.

**Then**
1. returns: `len(result) == 2`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `L2 in db.dirty`.
6. session: `len(db.dirty) == 1`.

## `LedgerService.get_item_movement_summary`

### LSV-IMS-01 — with both dates: the three lists, in range, of the workspace
- **Rules:** get_item_movement_summary R1, Returns; HR-16
- **Kind:** happy
- **Expect:** pass

**Given**
1. EM1 = mentry, but `performed_at T(5)`.
2. EM2 = mentry, but `performed_at T(20)`.
3. EI1 = ientry, but `performed_at T(6)`.
4. EM9 = mentry, but `workspace_id W2.id`, `machine_id M9.id`, `item_id I9.id`, `performed_at T(5)`.

**When**
- `result = svc.get_item_movement_summary(db, item_id=I1.id, workspace_id=W1.id, start_date=T(1), end_date=T(10))`.

**Then**
1. returns: `set(result.keys()) == {"machine", "project", "inventory"}`.
2. returns ids: `result["machine"]` is `[EM1.id]`.
3. returns ids: `result["inventory"]` is `[EI1.id]`.
4. returns: `result["project"] == []`.

### LSV-IMS-02 — pass-through BUG-341: another item's entries are left out
- **Rules:** get_item_movement_summary R1 [BUG-341]
- **Kind:** bug
- **Expect:** xfail BUG-341
- **Fails today on:** Then 2 (EM3 of I2 is returned too)

**Given**
1. EM1 = mentry, but `performed_at T(5)`.
2. EM3 = mentry, but `item_id I2.id`, `performed_at T(6)`.

**When**
- `result = svc.get_item_movement_summary(db, item_id=I1.id, workspace_id=W1.id, start_date=T(1), end_date=T(10))`.

**Then**
1. returns: `EM1.id in [r.id for r in result["machine"]]`.
2. returns ids: `result["machine"]` is `[EM1.id]`.

### LSV-IMS-03 — pass-through BUG-646: without dates the item's entries come back
- **Rules:** get_item_movement_summary R1 [BUG-646]
- **Kind:** bug
- **Expect:** xfail BUG-646
- **Fails today on:** Then 2 (the lists are empty without both dates)

**Given**
1. EM1 = mentry, but `performed_at T(5)`.
2. EM2 = mentry, but `performed_at T(20)`.
3. EI1 = ientry, but `performed_at T(6)`.

**When**
- `result = svc.get_item_movement_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `set(result.keys()) == {"machine", "project", "inventory"}`.
2. returns ids: `result["machine"]` is `[EM2.id, EM1.id]`.
3. returns ids: `result["inventory"]` is `[EI1.id]`.

### LSV-IMS-04 — BUG-648: skip and limit reach the manager
- **Rules:** get_item_movement_summary R2 [BUG-648]
- **Kind:** bug
- **Expect:** xfail BUG-648
- **Fails today on:** Then 1 (the call raises TypeError: no `skip` / `limit` parameter)

**Given**
1. 3 rows, k = 1 … 3: EMk = mentry, but `performed_at T(k + 1)`.

**When**
- `result = svc.get_item_movement_summary(db, item_id=I1.id, workspace_id=W1.id, start_date=T(1), end_date=T(10), skip=1, limit=1)`.

**Then**
1. returns ids: `result["machine"]` is `[EM2.id]`.

### LSV-IMS-05 — by default at most 100 entries per list
- **Rules:** get_item_movement_summary R1, R2 (default 100, holds today and after BUG-648)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, k = 0 … 100: Qk = mentry, but `performed_at datetime(2025, 6, 2) + timedelta(minutes=k)`.

**When**
- `result = svc.get_item_movement_summary(db, item_id=I1.id, workspace_id=W1.id, start_date=T(1), end_date=T(10))`.

**Then**
1. returns: `len(result["machine"]) == 100`.
2. returns: `Q0.id not in [r.id for r in result["machine"]]`.

### LSV-IMS-06 — the report neither commits nor rolls back
- **Rules:** get_item_movement_summary R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. EM1 = mentry, but `performed_at T(5)`.
2. pending Q.
3. edit E(EM1).

**When**
- `result = svc.get_item_movement_summary(db, item_id=I1.id, workspace_id=W1.id, start_date=T(1), end_date=T(10))`, inside spies.

**Then**
1. returns: `len(result["machine"]) == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.
5. session: `EM1 in db.dirty`.

## `LedgerService.get_transactions_by_user`

### LSV-TBU-01 — pass-through BUG-645: the user's entries per ledger
- **Rules:** get_transactions_by_user R1 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: no `get_by_performer` on the machine ledger DAO)

**Given**
1. MU = mentry, but `performed_by U2.id`, `performed_at T(2)`.
2. MV = mentry, but `performed_at T(3)` (by U1).
3. IU = ientry, but `performed_by U2.id`, `performed_at T(4)`.
4. IV = ientry, but `performed_at T(5)` (by U1).

**When**
- `result = svc.get_transactions_by_user(db, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `set(result.keys()) == {"machine", "project", "inventory"}`.
2. returns ids: `result["machine"]` is `[MU.id]`.
3. returns ids: `result["inventory"]` is `[IU.id]`.
4. returns: `result["project"] == []`.

### LSV-TBU-02 — pass-through BUG-645: a non-member id is accepted and only W1 entries can come back
- **Rules:** get_transactions_by_user R2 [BUG-645]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: no `get_by_performer` on the machine ledger DAO)

**Given**
1. M9E = mentry, but `workspace_id W2.id`, `machine_id M9.id`, `item_id I9.id`, `performed_by U9.id`.
2. I9E = ientry, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`, `performed_by U9.id`.

**When**
- `result = svc.get_transactions_by_user(db, user_id=U9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == {"machine": [], "project": [], "inventory": []}`.

### LSV-TBU-03 — an exception from the manager passes on with no commit and no rollback
- **Rules:** get_transactions_by_user R3; TC6
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `ERR = RuntimeError("mgr")`; `patch.object(svc.ledger_manager, "get_transactions_by_user", side_effect=ERR)`.
2. pending Q.

**When**
- `svc.get_transactions_by_user(db, user_id=U2.id, workspace_id=W1.id)` inside `with pytest.raises(RuntimeError) as exc:` inside spies.

**Then**
1. raises: `exc.value is ERR`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `Q in db.new`.

### LSV-TBU-04 — without skip and limit the defaults 0 and 100 reach the manager
- **Rules:** get_transactions_by_user R1 (defaults)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. `R = {"machine": [], "project": [], "inventory": []}`; `patch.object(svc.ledger_manager, "get_transactions_by_user", return_value=R) as mgr`.

**When**
- `result = svc.get_transactions_by_user(db, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is R`.
2. mock called: `mgr.call_count == 1`.
3. mock called: the call's arguments, bound to the manager signature `(session, user_id, workspace_id, start_date, end_date, skip, limit)` whether passed by position or keyword, give `skip == 0`.
4. mock called: the same bound arguments give `limit == 100`.
5. mock called: the same bound arguments give `start_date is None`, `end_date is None`, `user_id == U2.id`, `workspace_id == W1.id`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| all list methods: `limit >= 1`, `limit <= 100`, `skip >= 0` (BUG-642) | `/ledgers/...` endpoints (integration) | 422 for `limit=0`, `limit=101`, `skip=-1` |
| `get_item_movement_summary` R2 [BUG-648] endpoint part | `GET /ledgers/reports/item-movement/{item_id}/` | the endpoint accepts `skip`/`limit` (1–100) and passes them on |
| `get_machine_balance` R2, `get_inventory_balance` R3 [BUG-3043] JSON form | `GET /ledgers/machine/balance/`, `GET /ledgers/inventory/balance/` (integration) | `total_value` serialised as `"1234.50"` / `"0.00"` |
| `reconcile_machine_item` R9 [BUG-643], `reconcile_inventory` R7 [BUG-644]: the race and the lock held until commit | integration | two concurrent reconciles: the second waits until the first commits, then returns `balanced`; one adjustment row |
| `get_inventory_balance` R2 `InventoryTypeEnum` parsing | `GET /ledgers/inventory/balance/` | query string `STORAGE` reaches the service as the enum |
| manager rules R1–R11 of each method | `ledger_manager.cases.md` | filters, ordering, balances, reconcile rows |
| `get_item_movement_summary` R1 project list [BUG-647] | revisit after launch (projects deferred) | the item's project ledger entries |
| `get_project_component_total_cost` R2 [BUG-654], float form | revisit after launch (projects deferred) | net cost, money form |

## Spec gaps
None open. Closed in revision 2:

| # | Where | Resolution |
|---|---|---|
| 1 | deleted project on the component ledger / total cost | spec G1: new R1a [BUG-1278, BUG-1954] in both methods → LSV-PCL-10, LSV-PCT-07 (strict xfail). |
| 2 | exact lock clause | spec G2: `FOR UPDATE OF machine_items` (`reconcile_machine_item` R9), `FOR UPDATE OF inventory` (`reconcile_inventory` R7) → LSV-RMI-13, LSV-RINV-15 pinned. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_machine_ledger` | R1 | LSV-GML-01 … 07 |
| | R1 [BUG-640] | LSV-GML-10 |
| | R1 [BUG-341] | LSV-GML-11 |
| | R2 / TC6 | LSV-GML-08, 09 |
| `get_machine_balance` | R1 | LSV-GMB-01, 03, 05, 06 |
| | R1 [BUG-641] | LSV-GMB-08 |
| | R2 [BUG-3043] | LSV-GMB-01, 03 (pass part); 02, 04 (xfail) |
| | R3 / TC6 | LSV-GMB-07 |
| `reconcile_machine_item` | R1 | LSV-RMI-01, 02, 03 |
| | R2 | LSV-RMI-01; [BUG-649] RMI-08, 09 |
| | R3 | LSV-RMI-02, 04 |
| | R4 | LSV-RMI-05, 06, 08 |
| | R5 | LSV-RMI-07 |
| | R6 / TC1 | LSV-RMI-01, 03, 05 |
| | R7 / TC3 | LSV-RMI-10, 11 |
| | R8 / TC4 | LSV-RMI-12 |
| | R9 [BUG-643] | LSV-RMI-13 |
| | [BUG-650] | LSV-RMI-14 |
| `get_project_component_ledger` | R1 | LSV-PCL-05 … 08 |
| | R1a [BUG-1278, BUG-1954] | LSV-PCL-10 |
| | R2 | LSV-PCL-01 … 04, 11 |
| | R3 / TC6 | LSV-PCL-09 (refusal), LSV-PCL-11 (allowed) |
| `get_project_component_total_cost` | R1 | LSV-PCT-03, 04, 05 |
| | R1a [BUG-1278, BUG-1954] | LSV-PCT-07 |
| | R2 | LSV-PCT-01, 02 |
| | R3 / TC6 | LSV-PCT-06 |
| `get_inventory_ledger` | R1 | LSV-GIL-01 … 08 |
| | R2 / TC6 | LSV-GIL-09 |
| `get_inventory_balance` | R1 | LSV-GIB-01, 04, 07, 08 |
| | R1 [BUG-655] | LSV-GIB-06 |
| | R2 | LSV-GIB-01, 03, 04 |
| | R3 [BUG-3043] | LSV-GIB-01, 04 (pass part); 02, 05 (xfail) |
| | R4 / TC6 | LSV-GIB-09 |
| `reconcile_inventory` | R1 | LSV-RINV-01, 02, 03 |
| | R2 | LSV-RINV-01; [BUG-649] RINV-10, 11 |
| | R3 | LSV-RINV-02, 06 |
| | R4 [BUG-3042] | LSV-RINV-04 (pass part); 05, 17 (xfail) |
| | R5 | LSV-RINV-07, 08, 09, 10 |
| | R6 / TC1, TC3, TC4 | LSV-RINV-01, 03, 12, 13, 14 |
| | R7 [BUG-644] | LSV-RINV-15 |
| | [BUG-655] | LSV-RINV-16 |
| | [BUG-653] | LSV-RINV-17 |
| | [BUG-652] | LSV-RINV-18 |
| `get_attachment_ledger` | R1 | LSV-GAL-01 … 08 |
| | R2 / TC6 | LSV-GAL-09 |
| `get_item_movement_summary` | R1 | LSV-IMS-01, 05; [BUG-341] IMS-02; [BUG-646] IMS-03; project list deferred |
| | R2 [BUG-648] | LSV-IMS-04 (xfail), 05 (default, pass) |
| | R3 / TC6 | LSV-IMS-06 |
| `get_transactions_by_user` | R1 [BUG-645] | LSV-TBU-01 |
| | R1 (defaults, exact arguments) | LSV-TBU-04 |
| | R2 | LSV-TBU-02 |
| | R3 / TC6 | LSV-TBU-03 |
| Transaction contract | TC2, TC5 | not applicable (spec Notes: no re-read) |
