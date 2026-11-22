# Test cases — `app/services/account_invoice_service.py`

> **Spec:** `tests/unit/services/account_invoice_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — spec fill-gaps (Gap log G1–G8). G1 (L1a signatures): L-11's manager call by keyword; new L-16 (`prioritize_purchase_order_id` forwarded), L-17, L-18 (a filter forwarded on each list). G2 (K5a): K-02 now starts at `Planning` and expects `Receiving`; K-12 deletes only `Receiving` and checks the exact 422 text; new K-36 (`Complete` stays), K-37 (no `Draft` row: back-filled, no error). G3 (S6b): S-14 also checks `source_order_item_id`; new S-28 (`None` description / prices, whitespace description kept, `unit` None, quantity `0.00`). G4 (X1b): new X-23 (service line fulfilled without delivery blocks), X-24 (delivered then returned still blocks). G5: K-35 checks the preview. G6 (S1a, K3b, K9b, X1c): lock vocabulary rewritten (row lock / line lock); S-25, K-15, X-08 pin the clauses, X-08 adds the line lock and the order → lines → invoice order; new K-38 (sales order row lock on confirm), X-25 (sales row + line locks on void). G7: the S5 `Item <item_id>` fallback is unreachable, no card. G8 (K9a): K-33 checks that no section events are logged. No ID retired.
> **Revision:** 2a (2026-11-22) — wording only, from the executor: L-12 reads each event as a dict (`e["id"]`, not `e.id`). Counts unchanged.
> **Revision:** 3 (2026-11-22) — from `account_invoice_service.verify.md` (NEEDS WORK, case designer). Finding 1 (missing rollback not seen on create / update / revert): C-02, C-03, U-03, V-02 gain `session: X not in db` right after the call, before any `committed:` line. Finding 2 (non-HTTP error on void): new X-26 (`Author: claude`, **failing unconfirm** in Forced errors: the error reaches the caller as the same object, a rollback happened, nothing written, X gone). Finding 3 (commit count): new D-16 (delete with a PO) and S-29 (resync), each `cm.call_count == 1`, `rb.call_count == 0`, modelled on U-05. Finding 4 (HR-16 on void / delete): new D-17 (W0 PO), D-18 (W2 PO), X-27 (W0 PO, with a received line), X-28 (W2 PO). Finding 5: K-35 is now `xfail BUG-2965, BUG-1205` (Conventions explain a two-bug marker). Notes: X-09 step 6 split into two flushes (steps 6, 7); "before U" now requires U to be read at all; K-38 builds two approved approvers and checks the approvers are read (Then 4); K-31 now uses one approved and one pending approver and expects `Requires 2 approval(s); 1 so far`, which only a real read of the approvers gives. No ID retired.
> **Counts:** 149 cases · 106 expected-to-pass · 43 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `create_invoice` 6 · `get_invoice` 4 · read pass-throughs 18 · `update_invoice` 5 · `delete_invoice` 18 (6 bug) · `revert_to_draft` 7 (3 bug) · `resync_items` 29 (9 bug) · `confirm_invoice` 34 (14 bug; IDs K-26 … K-29 unused, the sales cards start at K-30) · `void_invoice` 28 (11 bug; the void-note schema card is here).
- **Depth:** full (skill step 1a). The service writes money (invoice status, payments) and order workflow state (PO sections, approvals, stage), and adds checks of its own on top of the manager.
- **Transaction contract:** TC1 + TC2 on every write's happy card; TC3 on every write with an **uncommitted** extra workspace X added after the commit point that must be gone afterwards (the only thing a missing rollback changes when the refusal comes before any write); TC4 on create, update, delete, resync, confirm and void; TC5 on create; "commits exactly once" on update, delete and resync (U-05, D-16, S-29); C-02, C-03, U-03, V-02 and X-26 check `X not in db` right after the call, so a missing service rollback shows before the test's own rollback (the refusals there come before any write); a non-HTTP error after writes on confirm (K-13) and void (X-26); TC6 on each read, both on success and on an error. `delete_invoice` has no TC2 (spec departure), its D3 card checks the object is not re-read.
- **Bugs (all strict):** BUG-2962 (locks) 5 statement-recorder cards; BUG-2963 3, BUG-2964 5, BUG-2965 5, BUG-2966 3, BUG-2967 3, BUG-2968 1, BUG-2969 6, BUG-2732 3; pass-throughs BUG-639, 1202, 2730 ×2, 2731, 2733, 2736, 2788, 626. Passing companions for what holds today and after the fix: a draft with payment history is never deleted (D-08), invoice_id cleared on delete (D-13), another workspace's order untouched (D-14, K-16, K-17, K-24, K-25, X-21), a sales order with every check met confirms (K-34), expense approvals untouched on void (X-19), a sales void with nothing delivered goes ahead (X-16), receiving-started revert refused with a loose text check (V-03).
- **Notable design choices:**
  - The forced-error cards patch an internal collaborator in the service module (not an external): K-13 `notify_invoice_action`, X-26 `purchase_order_manager.unconfirm_sections_after_invoice_void`. They are the only way to raise a non-HTTP error after writes. Declared under "Forced errors". `Author: claude`.
  - K-35 needs two fixes (BUG-2965 and BUG-1205) and carries both IDs.
  - The stage-row-missing cards delete standing statuses of W1 before the commit point: K-12 only `Receiving` (exact 422 text, K5a), K-37 only `Draft` (back-filled, no error), X-09 Planning / Receiving / Complete.
  - Lock cards pin the clause (S1a, K3b, K9b, X1c): one-table order / invoice reads end in `FOR UPDATE` (or `FOR UPDATE OF` that table), line reads in exactly `FOR UPDATE OF <lines table>`, never `SKIP LOCKED` / `NOWAIT`, and each lock is sent **before the guard's first read of its own rows** (approvers, lines, the linked order), so a later manager lock (BUG-621) cannot satisfy them. Lock order (row → lines → invoice) is checked only when an invoice lock exists, so the cards do not depend on BUG-621.
  - A W2 (and W0) order pointing at a W1 invoice is invalid data inserted on purpose (HR-16).
- **Needs a decision:** None. Revision-1 gaps 1–8 are closed by the spec's Gap log (see Spec gaps).

## Conventions for this module

**IDs.** `AIS` = `app/services/account_invoice_service.py`. `C` create_invoice · `G` get_invoice · `L` read pass-throughs · `U` update_invoice · `D` delete_invoice · `V` revert_to_draft · `S` resync_items · `K` confirm_invoice · `X` void_invoice (incl. the `VoidInvoiceRequest` schema card).

**Imports.** `svc` = `account_invoice_service` (`from app.services.account_invoice_service import AccountInvoiceService, account_invoice_service`). `mgr` = `account_invoice_manager` (`app.managers.account_invoice_manager`). Models from `app.models.<snake_case>`: `AccountInvoice`, `InvoiceItem`, `InvoicePayment`, `InvoiceEvent`, `Account`, `PurchaseOrder`, `PurchaseOrderItem`, `PurchaseOrderApprover`, `PurchaseOrderEvent`, `PurchaseOrderReturn`, `SalesOrder`, `SalesOrderItem`, `SalesOrderApprover`, `SalesOrderEvent`, `ExpenseOrder`, `ExpenseOrderItem`, `ExpenseOrderApprover`, `ExpenseOrderEvent`, `WorkOrder`, `WorkOrderEvent`, `WorkOrderType`, `Status`, `OrderWorkflow`, `Factory`, `Item`, `Workspace`, `WorkspaceMember`, `Notification`. Schemas from `app.schemas.account_invoice`: `AccountInvoiceCreate`, `AccountInvoiceUpdate`, `VoidInvoiceRequest`. `HTTPException` (fastapi), `pydantic.ValidationError`, `IntegrityError` (sqlalchemy.exc), `inspect`, `select`, `func`, `text` (sqlalchemy), `patch` (unittest.mock), `Decimal`, `date`, `datetime`, `uuid`. Every call: `db` first, the rest by keyword. `result` = what the When returns.

**Fixed values.** MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. T0 = `datetime(2026, 3, 1, 8, 0)`, T1 = `datetime(2026, 3, 4, 9, 0)`, T2 = `datetime(2026, 3, 4, 10, 0)`. Nothing is mocked unless a card says so. Long dashes in texts are U+2014; copy them. LOCK(kind) = `"Invoice is locked — the linked " + kind + " is completed. Correct it with a credit note or return."`. RCVTXT = `"Cannot revert to draft — goods have been received on the linked order. Record a return instead."`. CNTXT = `"Return credit notes cannot be reverted to draft. Void it and create a new return instead."`. RECVD = `"Cannot void invoice after receiving has been recorded on the linked order"`. CRT(**k) = `AccountInvoiceCreate(account_id=A1.id, invoice_type="payable", invoice_date=date(2026, 9, 1), **k)`, plus `invoice_amount=Decimal("0.00")` only if `"invoice_amount" in AccountInvoiceCreate.model_fields`.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`). U1 … U5 = `make_profile(db, name=…)`: `"Rahim Uddin"`, `"Bob Karim"`, `"Chitra Das"`, `"Dev Paul"`, `"Esha Roy"`.
2. `WorkspaceMember(workspace_id=…, user_id=…, role="member", status=…)`: U1, U2, U4 in W1 `"active"`; U5 in W1 `"inactive"`; U3 in **W2 only** `"active"`. U1 creates every Given row; **U2 is the acting user**.
3. For W0, W1, W2 (suffix `0`, `1`, `9`): SDk, SPk, SRk, SCk = `Status(workspace_id=…, name=…, comment="po stage")` named `"Draft"`, `"Planning"`, `"Receiving"`, `"Complete"`; WFk = `OrderWorkflow(workspace_id=…, name="Purchase Order", type="purchase", status_sequence=[SDk.id, SPk.id, SRk.id, SCk.id])`; Fk = `Factory(workspace_id=…, name="Main Plant", abbreviation=f"MP{k}", is_active=True, is_deleted=False)`; WTk = `WorkOrderType(workspace_id=…, name="Repair")`; Ak = `Account(workspace_id=…, name=…, is_active=True, is_deleted=False, allow_invoices=True)` named `"Zeta West"`, `"Acme Traders"`, `"Xeno Foreign"`.
4. W1 items: I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs", is_active=True)`; I2 = the same with `"Nut"`, `"nut"`, unit `"box"`.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but", a line lists every column that differs. "of W0" / "of W9" = workspace W0 / W2 and that workspace's A, F, WT, SD, WF. A line written as code is a step to run exactly.
- **inv** = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="payable", invoice_status="draft", payment_status="unpaid", invoice_amount=Decimal("0.00"), paid_amount=Decimal("0.00"), invoice_date=date(2026, 9, 1), allow_payments=True, receiving_started=False, created_by=U1.id)`; `order_type`, `order_id`, `description`, `void_note`, `last_synced_at` NULL. **confirmed** = `invoice_status "confirmed"`, `invoice_amount Decimal("400.00")`.
- **invl(V, s, k)** = `InvoiceItem(workspace_id=V.workspace_id, invoice_id=V.id, line_number=k, description="Old line", quantity=Decimal("1"), unit_price=Decimal(s), line_subtotal=Decimal(s), created_by=U1.id)`.
- **pay(V, a)** = `InvoicePayment(workspace_id=V.workspace_id, invoice_id=V.id, payment_amount=Decimal(a), payment_date=date(2026, 9, 2), is_voided=False, created_by=U1.id)`; any other required column filled neutrally as `mk_pay` of the manager tests. **voided pay** = `is_voided True`, `voided_at T0`, `voided_by U1.id`, `void_note "manual void"`.
- **po "n"** = `PurchaseOrder(workspace_id=W1.id, po_number=f"PO-{TAG}-n", account_id=A1.id, destination_type="storage", destination_id=F1.id, subtotal=Decimal("999.00"), total_amount=Decimal("999.00"), current_status_id=SD1.id, order_workflow_id=WF1.id, created_by=U1.id)`; `supplier_confirmed`, `details_confirmed`, `items_confirmed`, `invoice_confirmed`, `invoice_ever_linked`, `paid`, `voided` default `False`. **ready** = `supplier_confirmed True`, `details_confirmed True`, `items_confirmed True`. **of V** = `invoice_id V.id`, `invoice_ever_linked True`. **locked by V** = of V, ready, `invoice_confirmed True`, stage `current_status_id SR1.id`.
- **poline(O, k)** = `PurchaseOrderItem(workspace_id=O.workspace_id, purchase_order_id=O.id, line_number=k, item_id=I1.id, quantity_ordered=Decimal("10.00"), quantity_received=Decimal("0.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("20.00"))`.
- **poappr(O, U)** = `PurchaseOrderApprover(workspace_id=O.workspace_id, purchase_order_id=O.id, user_id=U.id, assigned_by=U1.id, approved=False, approved_at=None, assigned_at=T1)`. **approved** = `approved True`, `approved_at T2`.
- **so "n"** = `SalesOrder(workspace_id=W1.id, sales_order_number=f"SO-{TAG}-n", account_id=A1.id, factory_id=F1.id, current_status_id=SD1.id, order_date=date(2026, 9, 1), total_amount=Decimal("20000.00"), created_by=U1.id)`; `order_info_confirmed`, `items_confirmed`, `invoice_confirmed`, `is_invoiced`, `paid`, `order_completed` default `False`. **so ready** = `order_info_confirmed True`, `items_confirmed True`. **finalized by V** = so ready, `invoice_id V.id`, `invoice_confirmed True`, `is_invoiced True`.
- **soline(S)** = `SalesOrderItem(workspace_id=S.workspace_id, sales_order_id=S.id, item_id=I1.id, description="Chair", quantity_ordered=Decimal("10.00"), quantity_delivered=Decimal("0.00"), unit_price=Decimal("2000.00"), line_total=Decimal("20000.00"), requires_delivery=True)`.
- **soappr(S, U)** = `SalesOrderApprover(workspace_id=S.workspace_id, sales_order_id=S.id, user_id=U.id, assigned_at=T1)`; **approved** as above.
- **eo "n"** = `ExpenseOrder(workspace_id=W1.id, expense_number=n, expense_category="other", expense_date=date(2026, 9, 1), subtotal=Decimal("45000.00"), total_amount=Decimal("45000.00"), description="Machine repair", created_by=U1.id)`; `voided False`, `completed_at` NULL.
- **eoline(E, k)** = `ExpenseOrderItem(workspace_id=E.workspace_id, expense_order_id=E.id, line_number=k, description="Paper", quantity=Decimal("2"), unit="box", unit_price=Decimal("5.00"), line_subtotal=Decimal("10.00"))`. **eoappr(E, U)** = `ExpenseOrderApprover(workspace_id=E.workspace_id, expense_order_id=E.id, user_id=U.id, assigned_at=T1)`.
- **wo "n"** = `WorkOrder(workspace_id=W1.id, work_order_number=n, work_order_type_id=WT1.id, factory_id=F1.id, title="Pump repair", status="DRAFT", cost=Decimal("5000.00"), created_by=U1.id)`; `is_deleted False`.
- An order "of V" (SO / EO / WO) = `invoice_id V.id`.
- **commit point** = after the last Given line, `db.commit()` (a savepoint release under the `db` fixture). Snapshots for `unchanged` / `nothing written` are taken here. **X** (only where listed, after the commit point) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`.

**Named checks.**
- **re-read R** = `db.expire_all()`, then `db.get(type(R), R.id)`. **unchanged(R)** = after re-read, every column of R equals its commit-point snapshot. **gone(R)** = after `db.expire_all()`, `db.get(type(R), R.id) is None`. **x_gone** = `db.get(Workspace, X_ID) is None`.
- **EV(O)** = after `db.expire_all()`, O's rows in its own events table (`purchase_order_events.purchase_order_id`, `sales_order_events.sales_order_id`, `expense_order_events.expense_order_id`, `work_order_events.work_order_id`), ordered by `id`; **types(O)** = `[e.event_type for e in EV(O)]`; metadata is the `metadata_json` attribute. **IEV(V)** = `invoice_events` of V by id; **itypes(V)** = their `event_type` list. **LINES(V)** = V's `invoice_items` by `line_number`, after `db.expire_all()`.
- **notes()** = after `db.expire_all()`, all `Notification` rows by id; **recips()** = `sorted(n.recipient_user_id for n in notes())`.
- **nothing written** = the row counts (all workspaces) of `account_invoices`, `invoice_items`, `invoice_events`, `invoice_payments`, `purchase_order_events`, `purchase_order_approvers`, `sales_order_events`, `expense_order_events`, `work_order_events`, `notifications` equal their commit-point values.
- **session clean** = right after the call, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted`.
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(AccountInvoice).column_attrs})`; runs before any attribute of `r` is read.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads with a fresh query. `session: usable` = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself); `exc.value.status_code` / `exc.value.detail` compared with `==`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`.
- **Statement recorder** = an `after_cursor_execute` listener records every SQL statement sent during the When only. **lock(T)** = the first recorded SELECT whose `FROM` names table T and which contains `FOR UPDATE` (`None` if there is none). **row lock on T** = `lock(T)` is not None, its text (trailing spaces stripped) ends with `FOR UPDATE` or with `FOR UPDATE OF T`, and it contains neither `SKIP LOCKED` nor `NOWAIT`. **line lock on T** = `lock(T)` is not None, its text (trailing spaces stripped) ends with exactly `FOR UPDATE OF T`, and it contains neither `SKIP LOCKED` nor `NOWAIT`. **before U** = at least one recorded SELECT names table U in its `FROM`, and `lock(T)` is sent before the first of them (for U = a lines table, its own line lock may be that SELECT). So "before U" fails when U is never read. A recorder card ends its Given with `db.expunge_all()` after the commit point; ids come from objects built before.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n, BUG-m` = the same marker with a reason naming both (the card passes only when both are fixed). Write the call and checks as shown, also when the behaviour does not exist yet.

**Forced errors** (`Author: claude` cards only). **failing notify** = `with pytest.raises(RuntimeError) as exc:` around `with patch("app.services.account_invoice_service.notify_invoice_action", side_effect=RuntimeError("boom")):` around the When (K-13, `confirm_invoice` K6 / TC3). **failing unconfirm** = `E = RuntimeError("boom")`, then `with pytest.raises(RuntimeError) as exc:` around `with patch.object(app.services.account_invoice_service.purchase_order_manager, "unconfirm_sections_after_invoice_void", side_effect=E), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (X-26, `void_invoice` X6 / TC3: a non-HTTP error raised after the manager void, the approval reset and the unlink have written, before the commit).

**Race simulations.** None. Concurrency itself is integration-only; the lock cards check the emitted SQL.

## `AccountInvoiceService.create_invoice`

### AIS-C-01 — a new draft invoice is committed and returned re-read
- **Rules:** `create_invoice` C1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no invoices.

**When**
- `result = svc.create_invoice(db, invoice_in=CRT(description="Rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, AccountInvoice)`, `result.id is not None`, `result.created_at is not None`.
3. committed: the `account_invoices` row with `id == result.id` exists: `workspace_id == W1.id`, `account_id == A1.id`, `invoice_status == "draft"`, `description == "Rent"`, `created_by == U2.id`.
4. committed: `IEV(result)` has exactly 1 row.
5. committed: W1 has exactly 1 `account_invoices` row.

### AIS-C-02 — another workspace's account: the manager's 404 passes unchanged, nothing saved
- **Rules:** `create_invoice` C2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No invoices exist.
2. X (after the commit point).

**When**
- `svc.create_invoice(db, invoice_in=CRT(account_id=A9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Account with ID {A9.id} not found"`.
4. session: `X not in db` (checked right after the call: the service's rollback expunges the pending X).
5. session: session clean.
6. nothing written: nothing written.
7. committed: x_gone.
8. session: usable.

### AIS-C-03 — an account that does not allow invoices: the manager's 403 passes unchanged
- **Rules:** `create_invoice` C2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. `A1.allow_invoices = False`, then `db.flush()`.
2. X (after the commit point).

**When**
- `svc.create_invoice(db, invoice_in=CRT(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. session: `X not in db` (checked right after the call).
5. nothing written: nothing written.
6. committed: x_gone.

### AIS-C-04 — a deleted account: the manager's 400 passes unchanged
- **Rules:** `create_invoice` C2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. `A1.is_deleted = True`, `A1.is_active = False`, then `db.flush()`.

**When**
- `svc.create_invoice(db, invoice_in=CRT(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create invoice for deleted account"`.
4. nothing written: nothing written.

### AIS-C-05 — a failing commit is rolled back and re-raised; nothing saved
- **Rules:** `create_invoice` C1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no invoices.

**When**
- `svc.create_invoice(db, invoice_in=CRT(), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: W1 has exactly 0 `account_invoices` rows.
4. count: W1 has exactly 0 `invoice_events` rows.

### AIS-C-06 — a failing re-read after the commit leaves the invoice saved
- **Rules:** `create_invoice` C1; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no invoices.

**When**
- `svc.create_invoice(db, invoice_in=CRT(description="Rent"), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `account_invoices` row.
3. committed: that row has `description == "Rent"`, `invoice_status == "draft"`.

## `AccountInvoiceService.get_invoice`

### AIS-G-01 — returns the workspace's invoice; neither commits nor rolls back
- **Rules:** `get_invoice` G1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv.
2. X (after the commit point).

**When**
- spies: `result = svc.get_invoice(db, invoice_id=V.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, AccountInvoice)`, `result.id == V.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### AIS-G-02 — a W0 invoice (lower workspace id) gets the 404
- **Rules:** `get_invoice` G1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = inv of W0.
2. V = inv.

**When**
- `svc.get_invoice(db, invoice_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {Z.id} not found"`.

### AIS-G-03 — a W2 invoice (higher workspace id) gets the 404
- **Rules:** `get_invoice` G1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. Z = inv of W9.

**When**
- `svc.get_invoice(db, invoice_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {Z.id} not found"`.

### AIS-G-04 — a 404 neither rolls back nor drops a pending change
- **Rules:** `get_invoice` G1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. X (after the commit point).

**When**
- spies: `svc.get_invoice(db, invoice_id=MISSING, workspace_id=W1.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.detail == "Invoice with ID 999999999 not found"`.
2. mock called: `rb.call_count == 0`.
3. mock called: `cm.call_count == 0`.
4. session: `X in db`.

## Read pass-throughs

### AIS-L-01 — list_invoices: 101 invoices, no limit given → 100; nothing committed
- **Rules:** L1, L3; TC6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 invoices, built with `add_all` and one flush: inv, but `description f"I{k}"` for k = 1 … 101; `all_ids` = their ids.
2. X (after the commit point).

**When**
- spies: `result = svc.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len({r.id for r in result}) == 100`, `{r.id for r in result} <= all_ids`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### AIS-L-02 — list_invoices: limit=1000 is passed on
- **Rules:** L1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 invoices, built with `add_all` and one flush: inv, but `description f"I{k}"` for k = 1 … 101.

**When**
- `result = svc.list_invoices(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### AIS-L-03 — list_invoices: skip and limit are passed on; W0 and W2 rows never appear
- **Rules:** L1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = inv of W0.
2. 4 invoices VA, VB, VC, VD = inv, but `description` `"A"`, `"B"`, `"C"`, `"D"`.
3. Z2 = inv of W9.

**When**
- `result = svc.list_invoices(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len({r.id for r in result}) == 2`.
3. returns: `{r.id for r in result} <= {VA.id, VB.id, VC.id, VD.id}`.

### AIS-L-04 — list_invoices: skip alone is passed on
- **Rules:** L1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 3 invoices VA, VB, VC = inv, but `description` `"A"`, `"B"`, `"C"`.

**When**
- `result = svc.list_invoices(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {VA.id, VB.id, VC.id}`.

### AIS-L-05 — list_open_invoices_page: defaults skip 0 / limit 10
- **Rules:** L1, L3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 11 invoices, built with `add_all` and one flush: inv, but confirmed, `description f"O{k}"` for k = 1 … 11.

**When**
- spies: `result = svc.list_open_invoices_page(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `isinstance(result, tuple)`, `len(result[0]) == 10`.
2. returns: `result[1] == 11`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.

### AIS-L-06 — list_open_invoices_page: skip and limit=1000 are passed on
- **Rules:** L1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 11 invoices, built with `add_all` and one flush: inv, but confirmed, `description f"O{k}"` for k = 1 … 11.

**When**
- `result = svc.list_open_invoices_page(db, workspace_id=W1.id, account_id=A1.id, skip=10, limit=1000)`.

**Then**
1. returns: `len(result[0]) == 1`.
2. returns: `result[1] == 11`.

### AIS-L-07 — list_account_invoices_page: default limit is 50, not 100
- **Rules:** L2, L3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 invoices, built with `add_all` and one flush: inv, but confirmed, `description f"P{k}"` for k = 1 … 51.

**When**
- spies: `result = svc.list_account_invoices_page(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `len(result[0]) == 50`.
2. returns: `result[1] == 51`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.

### AIS-L-08 — list_account_invoices_page: skip and limit=1000 passed; other accounts and workspaces left out
- **Rules:** L2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A2 = `Account(workspace_id=W1.id, name="Beta Supplies", is_active=True, is_deleted=False, allow_invoices=True)`.
2. 51 invoices, built with `add_all` and one flush: inv, but confirmed, `description f"P{k}"` for k = 1 … 51.
3. VB = inv, but confirmed, `account_id A2.id`.
4. Z2 = inv of W9, but confirmed.

**When**
- `result = svc.list_account_invoices_page(db, workspace_id=W1.id, account_id=A1.id, skip=50, limit=1000)`.

**Then**
1. returns: `len(result[0]) == 1`.
2. returns: `result[1] == 51`.
3. returns: `result[0][0].account_id == A1.id`.

### AIS-L-09 — list_account_invoices_page is not open-only: a paid invoice is listed
- **Rules:** L2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. VP = inv, but confirmed, `paid_amount Decimal("400.00")`, `payment_status "paid"`.
2. VU = inv, but confirmed.

**When**
- `result = svc.list_account_invoices_page(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `{r.id for r in result[0]} == {VP.id, VU.id}`.
2. returns: `result[1] == 2`.

### AIS-L-10 — get_invoices_hub_summary returns the manager's tuple
- **Rules:** L1, L3
- **Kind:** happy
- **Expect:** pass

**Given**
1. VA = inv, but confirmed.
2. VB = inv, but confirmed, `invoice_type "receivable"`, `invoice_amount Decimal("150.00")`.
3. `expected = mgr.get_invoices_hub_summary(db, workspace_id=W1.id)` (after the commit point).

**When**
- spies: `result = svc.get_invoices_hub_summary(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == expected`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.

### AIS-L-11 — summarize_invoices returns the manager's tuple for the account
- **Rules:** L1, L3
- **Kind:** happy
- **Expect:** pass

**Given**
1. VA = inv, but confirmed.
2. VB = inv, but confirmed, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
3. `expected = mgr.summarize_invoices(db, workspace_id=W1.id, account_id=A1.id)` (after the commit point).

**When**
- spies: `result = svc.summarize_invoices(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `result == expected`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.

### AIS-L-12 — get_events returns the invoice's events
- **Rules:** L1, L3
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv.
2. E1 = `InvoiceEvent(workspace_id=W1.id, invoice_id=V.id, event_type="note", description="first", created_at=T1)`.
3. E2 = the same, but `description "second"`, `created_at T2`.

**When**
- spies: `result = svc.get_events(db, invoice_id=V.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e["id"] for e in result] == [e["id"] for e in mgr.get_events(db, V.id, W1.id)]` (each event is a dict).
2. returns: `{e["id"] for e in result} == {E1.id, E2.id}`.
3. mock called: `cm.call_count == 0`.

### AIS-L-13 — get_events: another workspace's invoice gets the 404, no rollback
- **Rules:** L1, L3; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = inv of W9.
2. X (after the commit point).

**When**
- spies: `svc.get_events(db, invoice_id=Z.id, workspace_id=W1.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Invoice with ID {Z.id} not found"`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### AIS-L-14 — get_items returns the invoice's lines
- **Rules:** L1, L3
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv.
2. L1 = invl(V, "150.00", 1).
3. L2 = invl(V, "250.00", 2).

**When**
- spies: `result = svc.get_items(db, invoice_id=V.id, workspace_id=W1.id)`.

**Then**
1. returns: `{i.id for i in result} == {L1.id, L2.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.

### AIS-L-15 — get_items: a missing invoice gets the 404
- **Rules:** L1
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.

**When**
- `svc.get_items(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Invoice with ID 999999999 not found"`.

### AIS-L-16 — list_open_invoices_page forwards prioritize_purchase_order_id
- **Rules:** L1, L1a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. VP = inv, but confirmed, `description "PO invoice"`, `order_type "purchase_order"`, `order_id O.id` (built first, so it has the lowest id and is not first without prioritising: the manager's default order is `invoice_date` desc, `id` desc).
3. 11 invoices, built with `add_all` and one flush: inv, but confirmed, `description f"O{k}"` for k = 1 … 11.
4. `expected = mgr.list_open_invoices_page(db, workspace_id=W1.id, account_id=A1.id, prioritize_purchase_order_id=O.id, skip=0, limit=1)` (after the commit point).

**When**
- `result = svc.list_open_invoices_page(db, workspace_id=W1.id, account_id=A1.id, prioritize_purchase_order_id=O.id, limit=1)`.

**Then**
1. returns: `[r.id for r in result[0]] == [r.id for r in expected[0]]`.
2. returns: `[r.id for r in result[0]] == [VP.id]`.
3. returns: `result[1] == 12`.

### AIS-L-17 — list_invoices forwards a filter
- **Rules:** L1, L1a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. VD = inv.
2. VC = inv, but confirmed.

**When**
- `result = svc.list_invoices(db, workspace_id=W1.id, invoice_status="confirmed")`.

**Then**
1. returns: `[r.id for r in result] == [VC.id]`.

### AIS-L-18 — list_account_invoices_page forwards a filter
- **Rules:** L2, L1a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. VP = inv, but confirmed.
2. VR = inv, but confirmed, `invoice_type "receivable"`.

**When**
- `result = svc.list_account_invoices_page(db, workspace_id=W1.id, account_id=A1.id, invoice_type="receivable")`.

**Then**
1. returns: `[r.id for r in result[0]] == [VR.id]`.
2. returns: `result[1] == 1`.

## `AccountInvoiceService.update_invoice`

### AIS-U-01 — a draft is updated and committed; its PO is not touched
- **Rules:** `update_invoice` U1, U2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv, but `description "Old desc"`.
2. O = po "1", but ready, of V.
3. P = poappr(O, U4), but approved.

**When**
- `result = svc.update_invoice(db, invoice_id=V.id, invoice_in=AccountInvoiceUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == V.id`.
3. committed: re-read V: `description == "New desc"`.
4. committed: unchanged(O).
5. committed: unchanged(P).
6. committed: `types(O) == []`.

### AIS-U-02 — a confirmed invoice's due date changes; its sales order is not touched
- **Rules:** `update_invoice` U1, U2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. S = so "1", but finalized by V.

**When**
- `result = svc.update_invoice(db, invoice_id=V.id, invoice_in=AccountInvoiceUpdate(due_date=date(2026, 12, 31)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `due_date == date(2026, 12, 31)`, `invoice_status == "confirmed"`.
3. committed: unchanged(S).
4. committed: `types(S) == []`.

### AIS-U-03 — another workspace's invoice: 404 passes unchanged, nothing saved
- **Rules:** `update_invoice` U1; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = inv of W9, but `description "Far"`.
2. X (after the commit point).

**When**
- `svc.update_invoice(db, invoice_id=Z.id, invoice_in=AccountInvoiceUpdate(description="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {Z.id} not found"`.
4. session: `X not in db` (checked right after the call).
5. session: session clean.
6. unchanged: unchanged(Z).
7. committed: x_gone.

### AIS-U-04 — a failing commit leaves the old description
- **Rules:** `update_invoice` U1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but `description "Old desc"`.

**When**
- `svc.update_invoice(db, invoice_id=V.id, invoice_in=AccountInvoiceUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read V: `description == "Old desc"`.

### AIS-U-05 — the update commits exactly once and does not roll back
- **Rules:** `update_invoice` U1; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv, but `description "Old desc"`.

**When**
- spies: `result = svc.update_invoice(db, invoice_id=V.id, invoice_in=AccountInvoiceUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.

## `AccountInvoiceService.delete_invoice`

### AIS-D-01 — a draft with no order is deleted and committed; the deleted object is returned
- **Rules:** `delete_invoice` D2, D3, D6; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv.
2. L = invl(V, "100.00", 1).
3. E = `InvoiceEvent(workspace_id=W1.id, invoice_id=V.id, event_type="note", description="n", created_at=T1)`.
4. `vid = V.id`.

**When**
- `result = svc.delete_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, AccountInvoice)`, `result.id == vid`.
2. committed: `db.get(AccountInvoice, vid) is None`.
3. committed: count of `invoice_items` with `invoice_id == vid`: exactly 0.
4. committed: count of `invoice_events` with `invoice_id == vid`: exactly 0.
5. committed: count of `purchase_order_events`, `sales_order_events`, `expense_order_events`, `work_order_events` rows (all workspaces): exactly 0.

### AIS-D-02 — the deleted object is not re-read
- **Rules:** `delete_invoice` D3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv.

**When**
- `with patch.object(db, "refresh", wraps=db.refresh) as rf:` around `result = svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. mock called: `rf.call_count == 0`.

### AIS-D-03 — the PO's draft invoice: the PO is unlinked with one event, sections and stage kept
- **Rules:** `delete_invoice` D1, D4; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv.
2. O = po "1", but of V, `supplier_confirmed True`, `details_confirmed True`, `current_status_id SP1.id`.

**When**
- `result = svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read O: `invoice_id is None`, `invoice_confirmed is False`, `paid is False`.
3. committed: re-read O: `supplier_confirmed is True`, `details_confirmed is True`, `items_confirmed is False`, `current_status_id == SP1.id`.
4. committed: `len(EV(O)) == 1`.
5. committed: `EV(O)[0].event_type == "invoice_draft_deleted"`, `EV(O)[0].performed_by == U2.id`.
6. committed: `EV(O)[0].description == f"Draft invoice #{V.id} deleted"`.

### AIS-D-04 — the PO's "draft invoice deleted" event names the deleted invoice in its metadata
- **Rules:** `delete_invoice` D4a [BUG-2968]
- **Kind:** bug
- **Expect:** xfail BUG-2968
- **Fails today on:** Then 3 (metadata is `{"invoice_id": None}`)

**Given**
1. V = inv.
2. O = po "1", but of V.
3. `vid = V.id`.

**When**
- `result = svc.delete_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == vid`.
2. event: `types(O) == ["invoice_draft_deleted"]`.
3. event: `EV(O)[0].metadata_json == {"invoice_id": vid}`.

### AIS-D-05 — a confirmed invoice is refused; the PO and its events are unchanged
- **Rules:** `delete_invoice` D1, Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V.
3. X (after the commit point).

**When**
- `svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only draft invoices can be deleted. This invoice is 'confirmed'. Use void instead."`.
4. session: session clean.
5. unchanged: unchanged(V).
6. unchanged: unchanged(O).
7. nothing written: nothing written.
8. committed: x_gone.

### AIS-D-06 — another workspace's invoice: 404, nothing deleted
- **Rules:** `delete_invoice` D1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = inv of W9.
2. X (after the commit point).

**When**
- `svc.delete_invoice(db, invoice_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).
5. committed: x_gone.

### AIS-D-07 — a draft with payment history is refused with the 400; nothing deleted
- **Rules:** `delete_invoice` D1, Errors row 4 [BUG-639]
- **Kind:** bug
- **Expect:** xfail BUG-639
- **Fails today on:** Then 1 (the call raises IntegrityError, not HTTPException: the database refuses to detach the voided payment)

**Given**
1. V = inv.
2. P = pay(V, "100.00"), but voided pay.
3. O = po "1", but of V.

**When**
- `svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Invoice has payment history — confirm and void it instead"`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(O).

### AIS-D-08 — a draft with payment history is never deleted (today and after the fix)
- **Rules:** `delete_invoice` D1 [BUG-639]; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. P = pay(V, "100.00"), but voided pay.
3. O = po "1", but of V.
4. X (after the commit point).

**When**
- `svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`, wrapped in `with pytest.raises(Exception):`.

**Then**
1. re-read V: `V is not None`, `invoice_status == "draft"`.
2. re-read P: `P is not None`, `is_voided is True`.
3. unchanged: unchanged(O).
4. count: `types(O) == []`.
5. committed: x_gone.

### AIS-D-09 — a completed sales order's draft invoice is frozen: 400, nothing deleted
- **Rules:** `delete_invoice` D1, Errors row 3 [BUG-2730]
- **Kind:** bug
- **Expect:** xfail BUG-2730
- **Fails today on:** Then 1 (no error: the draft is deleted)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. S = so "1", but so ready, of V, `order_completed True`.

**When**
- `svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == LOCK("sales order")`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(S).

### AIS-D-10 — a sales order's draft invoice: the order is unlinked with its event
- **Rules:** `delete_invoice` D5 [BUG-2732]
- **Kind:** bug
- **Expect:** xfail BUG-2732
- **Fails today on:** Then 3 (`is_invoiced` stays True)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. S = so "1", but of V, `is_invoiced True`.
3. `vid = V.id`.

**When**
- `result = svc.delete_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == vid`.
2. committed: re-read S: `invoice_id is None`.
3. committed: re-read S: `is_invoiced is False`, `invoice_confirmed is False`, `paid is False`.
4. committed: `types(S) == ["invoice_draft_deleted"]`.
5. committed: `EV(S)[0].description == f"Draft invoice #{vid} deleted"`, `EV(S)[0].performed_by == U2.id`.
6. committed: `EV(S)[0].metadata_json == {"invoice_id": vid}`.

### AIS-D-11 — an expense order's draft invoice: the order logs the delete
- **Rules:** `delete_invoice` D5 [BUG-2732]
- **Kind:** bug
- **Expect:** xfail BUG-2732
- **Fails today on:** Then 3 (no expense order event is written)

**Given**
1. V = inv.
2. E = eo "EXP-2026-009", but of V.
3. `vid = V.id`.

**When**
- `result = svc.delete_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == vid`.
2. committed: re-read E: `invoice_id is None`.
3. committed: `types(E) == ["invoice_draft_deleted"]`.
4. committed: `EV(E)[0].description == f"Draft invoice #{vid} deleted"`, `EV(E)[0].performed_by == U2.id`.
5. committed: `EV(E)[0].metadata_json == {"invoice_id": vid}`.

### AIS-D-12 — a work order's draft invoice: the order logs the delete
- **Rules:** `delete_invoice` D5 [BUG-2732]
- **Kind:** bug
- **Expect:** xfail BUG-2732
- **Fails today on:** Then 3 (no work order event is written)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. WO = wo "WO-2026-031", but of V.
3. `vid = V.id`.

**When**
- `result = svc.delete_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == vid`.
2. committed: re-read WO: `invoice_id is None`.
3. committed: `types(WO) == ["invoice_draft_deleted"]`.
4. committed: `EV(WO)[0].description == f"Draft invoice #{vid} deleted"`, `EV(WO)[0].performed_by == U2.id`.
5. committed: `EV(WO)[0].metadata_json == {"invoice_id": vid}`.

### AIS-D-13 — sales, expense and work orders no longer point at the deleted invoice
- **Rules:** `delete_invoice` D5 (link cleared; holds today through the database and after the fix)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv.
2. S = so "1", but of V.
3. E = eo "EXP-2026-009", but of V.
4. WO = wo "WO-2026-031", but of V.

**When**
- `result = svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read S: `invoice_id is None`.
3. committed: re-read E: `invoice_id is None`.
4. committed: re-read WO: `invoice_id is None`.

### AIS-D-14 — another workspace's sales order pointing at the invoice keeps its flags and gets no event
- **Rules:** `delete_invoice` D5 (other workspace never touched); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. S9 = so "9" of W9, but `invoice_id V.id`, `is_invoiced True`, `current_status_id SD9.id`.

**When**
- `result = svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read S9: `is_invoiced is True`.
3. committed: `types(S9) == []`.

### AIS-D-15 — a failing commit keeps the invoice and the PO link
- **Rules:** `delete_invoice` D2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. O = po "1", but of V.

**When**
- `svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read V: `V is not None`.
4. re-read O: `invoice_id == V.id`.
5. count: `types(O) == []`.

### AIS-D-16 — delete commits exactly once and does not roll back
- **Rules:** `delete_invoice` D2, D4; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv.
2. O = po "1", but of V.

**When**
- spies: `result = svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: re-read O: `invoice_id is None`.
5. committed: `types(O) == ["invoice_draft_deleted"]`.

### AIS-D-17 — a W0 PO pointing at the draft is not "the PO's invoice": it keeps its flags and gets no event
- **Rules:** `delete_invoice` D1, D4, D6; Overview "The PO's invoice"; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. Z0 = po "0" of W0, but `invoice_id V.id`, `invoice_ever_linked True`, `invoice_confirmed True`, `paid True`.

**When**
- `result = svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: gone(V).
3. committed: re-read Z0: `invoice_confirmed is True`, `paid is True`.
4. committed: `types(Z0) == []`.

### AIS-D-18 — a W2 PO pointing at the draft is not "the PO's invoice": it keeps its flags and gets no event
- **Rules:** `delete_invoice` D1, D4, D6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. Z2 = po "9" of W9, but `invoice_id V.id`, `invoice_ever_linked True`, `invoice_confirmed True`, `paid True`.

**When**
- `result = svc.delete_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: gone(V).
3. committed: re-read Z2: `invoice_confirmed is True`, `paid is True`.
4. committed: `types(Z2) == []`.

## `AccountInvoiceService.revert_to_draft`

### AIS-V-01 — a confirmed PO invoice goes back to draft; the PO is not touched
- **Rules:** `revert_to_draft` V1, V2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V.
3. P = poappr(O, U4), but approved.

**When**
- `result = svc.revert_to_draft(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == V.id`.
3. committed: re-read V: `invoice_status == "draft"`.
4. committed: unchanged(O).
5. committed: unchanged(P).
6. committed: `types(O) == []`.

### AIS-V-02 — active payments: the manager's 400 passes unchanged, nothing saved
- **Rules:** `revert_to_draft` V1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").
3. X (after the commit point).

**When**
- `svc.revert_to_draft(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot revert to draft — invoice has active payments. Void all payments first."`.
4. session: `X not in db` (checked right after the call).
5. session: session clean.
6. unchanged: unchanged(V).
7. nothing written: nothing written.
8. committed: x_gone.

### AIS-V-03 — receiving started: refused with a 400 about receiving; nothing saved
- **Rules:** `revert_to_draft` V1
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `receiving_started True`.
2. O = po "1", but locked by V.

**When**
- `svc.revert_to_draft(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail.startswith("Cannot revert to draft — ")` and `"receiv" in exc.value.detail` (loose on purpose: today's text and RCVTXT both match).
4. unchanged: unchanged(V).
5. unchanged: unchanged(O).

### AIS-V-04 — receiving started: the detail is the BUG-2736 text
- **Rules:** `revert_to_draft` V1 [BUG-2736]
- **Kind:** bug
- **Expect:** xfail BUG-2736
- **Fails today on:** Then 2 (today's text advises zeroing received quantities)

**Given**
1. V = inv, but confirmed, `receiving_started True`.

**When**
- `svc.revert_to_draft(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == RCVTXT`.

### AIS-V-05 — a completed expense order's invoice is frozen
- **Rules:** `revert_to_draft` V1 [BUG-2730]
- **Kind:** bug
- **Expect:** xfail BUG-2730
- **Fails today on:** Then 1 (no error: the invoice is reverted)

**Given**
1. V = inv, but confirmed.
2. E = eo "EXP-2026-009", but of V, `completed_at T0`.

**When**
- `svc.revert_to_draft(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == LOCK("expense order")`.
4. unchanged: unchanged(V).

### AIS-V-06 — a return credit note cannot be reverted
- **Rules:** `revert_to_draft` V1 [BUG-2733]
- **Kind:** bug
- **Expect:** xfail BUG-2733
- **Fails today on:** Then 1 (no error: the credit note is reverted)

**Given**
1. O = po "1", but ready.
2. CN = inv, but confirmed, `invoice_type "receivable"`, `order_type "purchase_order"`, `order_id O.id`.
3. R = `PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O.id, return_number=f"PR-{TAG}-1", return_type="refund", created_by=U1.id, invoice_id=CN.id)`.

**When**
- `svc.revert_to_draft(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == CNTXT`.
4. unchanged: unchanged(CN).

### AIS-V-07 — a draft cannot be reverted: 400 passes unchanged
- **Rules:** `revert_to_draft` V1
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.

**When**
- `svc.revert_to_draft(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only confirmed invoices can be reverted to draft. Current status: 'draft'."`.
4. unchanged: unchanged(V).

## `AccountInvoiceService.resync_items`

### AIS-S-01 — a PO invoice is rebuilt from the PO lines in line order and committed
- **Rules:** `resync_items` S4, S5; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po "1", but ready.
2. V = inv, but `order_type "purchase_order"`, `order_id O.id`.
3. OL = invl(V, "999.00", 1).
4. PL2 = poline(O, 2).
5. PL1 = poline(O, 1), but `item_id I2.id`, `quantity_ordered Decimal("3.00")`, `unit_price Decimal("5.00")`, `line_subtotal Decimal("15.00")`.

**When**
- `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == V.id`.
3. committed: `[l.line_number for l in LINES(V)] == [1, 2]`.
4. committed: `LINES(V)[0]`: `description == "Nut"`, `item_id == I2.id`, `source_order_item_id == PL1.id`, `source_order_item_type == "po_item"`, `quantity == Decimal("3.00")`, `unit == "box"`, `unit_price == Decimal("5.00")`, `line_subtotal == Decimal("15.00")`.
5. committed: `LINES(V)[1]`: `description == "Bolt"`, `item_id == I1.id`, `source_order_item_id == PL2.id`, `unit == "pcs"`, `line_subtotal == Decimal("20.00")`.
6. committed: gone(OL).
7. committed: re-read V: `invoice_amount == Decimal("35.00")`, `payment_status == "unpaid"`, `last_synced_at is not None`, `invoice_status == "draft"`.
8. committed: `itypes(V) == ["items_synced"]`.
9. committed: `IEV(V)[0].description == "Items synced from order (2 lines)"`.
10. committed: unchanged(O).

### AIS-S-02 — a voided PO is still found and its lines are used
- **Rules:** `resync_items` S5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1", but `voided True`.
2. V = inv, but `order_type "purchase_order"`, `order_id O.id`.
3. PL = poline(O, 1).

**When**
- `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `len(LINES(V)) == 1`.
3. committed: `LINES(V)[0].source_order_item_id == PL.id`.

### AIS-S-03 — a missing PO: 404, old lines kept, nothing saved
- **Rules:** `resync_items` S5, Errors row 4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but `order_type "purchase_order"`, `order_id MISSING`.
2. OL = invl(V, "999.00", 1).
3. X (after the commit point).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Purchase order with ID 999999999 not found"`.
4. session: session clean.
5. unchanged: unchanged(OL).
6. nothing written: nothing written.
7. committed: x_gone.

### AIS-S-04 — a W0 PO (lower workspace id) is not found
- **Rules:** `resync_items` S5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = po "0" of W0.
2. poline(Z0, 1).
3. V = inv, but `order_type "purchase_order"`, `order_id Z0.id`.
4. OL = invl(V, "999.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Purchase order with ID {Z0.id} not found"`.
4. unchanged: unchanged(OL).

### AIS-S-05 — a W2 PO (higher workspace id) is not found
- **Rules:** `resync_items` S5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv, but `order_type "purchase_order"`.
2. OL = invl(V, "999.00", 1).
3. Z2 = po "9" of W9.
4. poline(Z2, 1).
5. `V.order_id = Z2.id`, then `db.flush()`.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Purchase order with ID {Z2.id} not found"`.
4. unchanged: unchanged(OL).

### AIS-S-06 — an unpriced PO line fails at flush; old lines kept, nothing saved
- **Rules:** `resync_items` S5, Errors row 7; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. PL = poline(O, 1), but `unit_price None`, `line_subtotal None`.
3. V = inv, but `order_type "purchase_order"`, `order_id O.id`.
4. OL = invl(V, "999.00", 1).
5. X (after the commit point).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError`.
2. unchanged: unchanged(OL).
3. unchanged: unchanged(V).
4. nothing written: nothing written.
5. committed: x_gone.
6. session: usable.

### AIS-S-07 — a confirmed invoice cannot be resynced
- **Rules:** `resync_items` S2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = po "1".
2. poline(O, 1).
3. V = inv, but confirmed, `order_type "purchase_order"`, `order_id O.id`.
4. OL = invl(V, "400.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Can only resync items on draft invoices."`.
4. unchanged: unchanged(OL).
5. nothing written: nothing written.

### AIS-S-08 — a voided invoice cannot be resynced
- **Rules:** `resync_items` S2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. V = inv, but `invoice_status "voided"`, `void_note "Old reason"`, `order_type "purchase_order"`, `order_id O.id`.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Can only resync items on draft invoices."`.
4. unchanged: unchanged(V).

### AIS-S-09 — an unlinked invoice that is not a draft gets the draft error first
- **Rules:** `resync_items` S2, S3 (order of checks)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv, but confirmed.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Can only resync items on draft invoices."`.

### AIS-S-10 — order_id None: not linked
- **Rules:** `resync_items` S3, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but `order_type "purchase_order"`.
2. OL = invl(V, "999.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is not linked to an order — resync is not applicable."`.
4. unchanged: unchanged(OL).
5. nothing written: nothing written.

### AIS-S-11 — order_id 0: not linked
- **Rules:** `resync_items` S3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv, but `order_type "purchase_order"`, `order_id 0`.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is not linked to an order — resync is not applicable."`.

### AIS-S-12 — order_type None with an order id: not linked
- **Rules:** `resync_items` S3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. V = inv, but `order_id O.id`.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is not linked to an order — resync is not applicable."`.

### AIS-S-13 — order_type "" with an order id: not linked
- **Rules:** `resync_items` S3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po "1".
2. V = inv, but `order_type ""`, `order_id O.id`.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is not linked to an order — resync is not applicable."`.

### AIS-S-14 — an expense order invoice is rebuilt from its lines, renumbered 1, 2
- **Rules:** `resync_items` S4, S6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "EXP-2026-009".
2. EL9 = eoline(E, 9), but `description ""`, `quantity Decimal("0")`, `unit_price Decimal("7.00")`, `line_subtotal Decimal("7.00")`.
3. EL5 = eoline(E, 5).
4. V = inv, but `order_type "expense_order"`, `order_id E.id`.
5. OL = invl(V, "999.00", 1).

**When**
- `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `[l.line_number for l in LINES(V)] == [1, 2]`.
3. committed: `LINES(V)[0]`: `description == "Paper"`, `item_id is None`, `source_order_item_id == EL5.id`, `source_order_item_type == "eo_item"`, `quantity == Decimal("2")`, `unit == "box"`, `unit_price == Decimal("5.00")`, `line_subtotal == Decimal("10.00")`.
4. committed: `LINES(V)[1]`: `description == f"Expense item {EL9.id}"`, `source_order_item_id == EL9.id`, `quantity == Decimal("1")`, `line_subtotal == Decimal("7.00")`.
5. committed: gone(OL).
6. committed: re-read V: `invoice_amount == Decimal("17.00")`.
7. committed: `IEV(V)[0].description == "Items synced from order (2 lines)"`.
8. committed: unchanged(E).

### AIS-S-15 — another workspace's expense order is not found
- **Rules:** `resync_items` S6, Errors row 4; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv, but `order_type "expense_order"`.
2. OL = invl(V, "999.00", 1).
3. E9 = eo "EXP-2026-900" of W9.
4. eoline(E9, 1).
5. `V.order_id = E9.id`, then `db.flush()`.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {E9.id} not found"`.
4. unchanged: unchanged(OL).

### AIS-S-16 — a missing expense order: 404
- **Rules:** `resync_items` S6, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but `order_type "expense_order"`, `order_id MISSING`.

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. nothing written: nothing written.

### AIS-S-17 — a sales order invoice is rebuilt from the order lines
- **Rules:** `resync_items` S4, S6a [BUG-2963]
- **Kind:** bug
- **Expect:** xfail BUG-2963
- **Fails today on:** Then 1 (the call raises AttributeError: the sales manager has no `get_sales_order`)

**Given**
1. S = so "1".
2. LA = soline(S).
3. LB = soline(S), but `item_id None`, `description "Crate"`, `quantity_ordered Decimal("2.00")`, `unit_price Decimal("50.00")`, `line_total Decimal("100.00")`.
4. V = inv, but `invoice_type "receivable"`, `order_type "sales_order"`, `order_id S.id`.
5. OL = invl(V, "999.00", 1).

**When**
- `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `[l.line_number for l in LINES(V)] == [1, 2]`.
3. committed: `LINES(V)[0]`: `description == "Bolt"`, `item_id == I1.id`, `source_order_item_id == LA.id`, `source_order_item_type == "so_item"`, `quantity == Decimal("10.00")`, `unit == "pcs"`, `unit_price == Decimal("2000.00")`, `line_subtotal == Decimal("20000.00")`.
4. committed: `LINES(V)[1]`: `description == "Crate"`, `item_id is None`, `unit is None`, `source_order_item_id == LB.id`, `line_subtotal == Decimal("100.00")`.
5. committed: re-read V: `invoice_amount == Decimal("20100.00")`.
6. committed: `IEV(V)[0].description == "Items synced from order (2 lines)"`.

### AIS-S-18 — a missing sales order: 404, lines kept
- **Rules:** `resync_items` S6a, Errors row 5 [BUG-2963]
- **Kind:** bug
- **Expect:** xfail BUG-2963
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. V = inv, but `invoice_type "receivable"`, `order_type "sales_order"`, `order_id MISSING`.
2. OL = invl(V, "999.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Sales order with ID 999999999 not found"`.
4. unchanged: unchanged(OL).

### AIS-S-19 — another workspace's sales order: 404
- **Rules:** `resync_items` S6a [BUG-2963]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2963
- **Fails today on:** Then 1 (the call raises AttributeError, not HTTPException)

**Given**
1. S9 = so "9" of W9, but `current_status_id SD9.id`.
2. V = inv, but `invoice_type "receivable"`, `order_type "sales_order"`, `order_id S9.id`.
3. OL = invl(V, "999.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Sales order with ID {S9.id} not found"`.
4. unchanged: unchanged(OL).

### AIS-S-20 — a work order invoice is rebuilt as its one labour line
- **Rules:** `resync_items` S4, S7 [BUG-2964]
- **Kind:** bug
- **Expect:** xfail BUG-2964
- **Fails today on:** Then 2 (every line is deleted: 0 lines)

**Given**
1. WO = wo "WO-2026-031".
2. V = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("5000.00")`, `order_type "work_order"`, `order_id WO.id`.
3. OL = invl(V, "5000.00", 1).

**When**
- `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `len(LINES(V)) == 1`.
3. committed: `LINES(V)[0]`: `line_number == 1`, `description == "Pump repair"`, `item_id is None`, `source_order_item_id is None`, `source_order_item_type == "wo_labor"`, `quantity == Decimal("1")`, `unit is None`, `unit_price == Decimal("5000.00")`, `line_subtotal == Decimal("5000.00")`.
4. committed: re-read V: `invoice_amount == Decimal("5000.00")`, `payment_status == "unpaid"`.
5. committed: `IEV(V)[0].description == "Items synced from order (1 lines)"`.

### AIS-S-21 — a work order with no cost gives one 0.00 line
- **Rules:** `resync_items` S7 [BUG-2964]
- **Kind:** bug
- **Expect:** xfail BUG-2964
- **Fails today on:** Then 2 (every line is deleted: 0 lines)

**Given**
1. WO = wo "WO-2026-031", but `cost None`.
2. V = inv, but `invoice_type "receivable"`, `order_type "work_order"`, `order_id WO.id`.
3. OL = invl(V, "5000.00", 1).

**When**
- `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `len(LINES(V)) == 1`.
3. committed: `LINES(V)[0].unit_price == Decimal("0.00")`, `LINES(V)[0].line_subtotal == Decimal("0.00")`.

### AIS-S-22 — a soft-deleted work order is not found; lines kept
- **Rules:** `resync_items` S7, Errors row 5 [BUG-2964]
- **Kind:** bug
- **Expect:** xfail BUG-2964
- **Fails today on:** Then 1 (no error: every line is deleted)

**Given**
1. WO = wo "WO-2026-031", but `is_deleted True`.
2. V = inv, but `invoice_type "receivable"`, `order_type "work_order"`, `order_id WO.id`.
3. OL = invl(V, "5000.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {WO.id} not found"`.
4. unchanged: unchanged(OL).
5. nothing written: nothing written.

### AIS-S-23 — another workspace's work order is not found
- **Rules:** `resync_items` S7 [BUG-2964]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2964
- **Fails today on:** Then 1 (no error: every line is deleted)

**Given**
1. WO9 = wo "WO-2026-900" of W9.
2. V = inv, but `invoice_type "receivable"`, `order_type "work_order"`, `order_id WO9.id`.
3. OL = invl(V, "5000.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {WO9.id} not found"`.
4. unchanged: unchanged(OL).

### AIS-S-24 — an unknown order type is refused and the lines are kept
- **Rules:** `resync_items` S8, Errors row 6 [BUG-2964]
- **Kind:** bug
- **Expect:** xfail BUG-2964
- **Fails today on:** Then 1 (no error: every line is deleted and the invoice becomes 0.00 "paid")

**Given**
1. V = inv, but `invoice_amount Decimal("400.00")`, `order_type "transfer_order"`, `order_id 7`.
2. OL = invl(V, "400.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Resync is not supported for order type 'transfer_order'."`.
4. unchanged: unchanged(OL).
5. unchanged: unchanged(V).
6. nothing written: nothing written.

### AIS-S-25 — the invoice is locked before the linked order is read
- **Rules:** `resync_items` S1, S1a [BUG-2962]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2962
- **Fails today on:** Then 2 (the invoice is read without `FOR UPDATE` before the order)

**Given**
1. E = eo "EXP-2026-009".
2. eoline(E, 1).
3. V = inv, but `order_type "expense_order"`, `order_id E.id`.
4. `vid = V.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.resync_items(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == vid`.
2. statement: row lock on `account_invoices`, before `expense_orders`.
3. statement: `"JOIN" not in lock("account_invoices")`.

### AIS-S-26 — a failing commit keeps the old lines
- **Rules:** `resync_items` S4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "EXP-2026-009".
2. eoline(E, 1).
3. V = inv, but `order_type "expense_order"`, `order_id E.id`.
4. OL = invl(V, "999.00", 1).

**When**
- `svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(OL).
4. count: `len(LINES(V)) == 1`.
5. count: `IEV(V) == []`.

### AIS-S-28 — expense lines with empty values: None description and prices, whitespace kept, quantity 0.00
- **Rules:** `resync_items` S6, S6b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "EXP-2026-009".
2. EA = eoline(E, 4), but `description None`, `quantity Decimal("0.00")`, `unit None`, `unit_price None`, `line_subtotal None`.
3. EB = eoline(E, 8), but `description "  "`, `unit_price Decimal("0.00")`, `line_subtotal Decimal("0.00")`.
4. V = inv, but `order_type "expense_order"`, `order_id E.id`.

**When**
- `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `[l.line_number for l in LINES(V)] == [1, 2]`.
3. committed: `LINES(V)[0]`: `description == f"Expense item {EA.id}"`, `source_order_item_id == EA.id`, `quantity == Decimal("1")`, `unit is None`, `unit_price == Decimal("0")`, `line_subtotal == Decimal("0")`.
4. committed: `LINES(V)[1]`: `description == "  "`, `source_order_item_id == EB.id`, `quantity == Decimal("2")`, `unit_price == Decimal("0.00")`, `line_subtotal == Decimal("0.00")`.
5. committed: re-read V: `invoice_amount == Decimal("0.00")`.

### AIS-S-27 — another workspace's invoice: 404
- **Rules:** `resync_items` S1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = inv of W9, but `order_type "purchase_order"`, `order_id MISSING`.

**When**
- `svc.resync_items(db, invoice_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Invoice with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### AIS-S-29 — resync commits exactly once and does not roll back
- **Rules:** `resync_items` S4; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "EXP-2026-009".
2. eoline(E, 1).
3. V = inv, but `order_type "expense_order"`, `order_id E.id`.
4. invl(V, "999.00", 1).

**When**
- spies: `result = svc.resync_items(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: `len(LINES(V)) == 1`.

## `AccountInvoiceService.confirm_invoice`

### AIS-K-01 — a manual invoice is confirmed at its line sum and committed; nobody notified
- **Rules:** `confirm_invoice` K1, K4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv, but `invoice_amount Decimal("1000.00")`.
2. invl(V, "150.00", 1).
3. invl(V, "250.00", 2).

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == V.id`.
3. committed: re-read V: `invoice_status == "confirmed"`, `invoice_amount == Decimal("400.00")`, `payment_status == "unpaid"`.
4. committed: `itypes(V) == ["confirmed"]`.
5. committed: `notes() == []`.

### AIS-K-02 — the PO's invoice: confirmed at the line sum, not the PO total; PO follow-ups committed together
- **Rules:** `confirm_invoice` K4, K5, K5a; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V, `current_status_id SP1.id`.
4. poappr(O, U4), but approved.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`, `invoice_amount == Decimal("400.00")`.
3. committed: re-read O: `invoice_confirmed is True`, `supplier_confirmed is True`, `details_confirmed is True`, `items_confirmed is True`.
4. committed: re-read O: `current_status_id == SR1.id`.
5. committed: `types(O) == ["invoice_created", "invoice_confirmed", "status_updated", "invoice_confirmed"]`.
6. committed: `EV(O)[-1].description == f"Invoice #{V.id} confirmed — order locked"`, `EV(O)[-1].performed_by == U2.id`.
7. committed: `EV(O)[-1].metadata_json == {"invoice_id": V.id}`.

### AIS-K-03 — the PO's invoice: approvers and creator are notified once each, inactive members skipped
- **Rules:** `confirm_invoice` K6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V.
4. poappr(O, U4), but approved.
5. poappr(O, U5), but approved.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `recips() == sorted([U1.id, U4.id])`.
3. committed: every row of `notes()`: `notification_type == "invoice_action"`, `entity_type == "purchase_order"`, `entity_id == O.id`, `source_type == "invoice"`, `source_id == V.id`, `actor_user_id == U2.id`.
4. committed: every row of `notes()`: `preview == f"confirmed|Invoice confirmed on PO-{O.id} — order locked"`.

### AIS-K-04 — PO items not confirmed: 400, nothing written
- **Rules:** `confirm_invoice` K2, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but of V, `supplier_confirmed True`, `details_confirmed True`.
4. poappr(O, U4), but approved.
5. X (after the commit point).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Confirm supplier, order details, and items before finalizing"`.
4. session: session clean.
5. unchanged: unchanged(V).
6. unchanged: unchanged(O).
7. nothing written: nothing written.
8. committed: x_gone.

### AIS-K-05 — the section check comes before the invoice's own status
- **Rules:** `confirm_invoice` K2 (order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. invl(V, "400.00", 1).
3. O = po "1", but of V, `details_confirmed True`, `items_confirmed True`.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Confirm supplier, order details, and items before finalizing"`.
4. unchanged: unchanged(V).

### AIS-K-06 — one approver not approved: 400 with the counts, nothing written
- **Rules:** `confirm_invoice` K3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V.
4. P = poappr(O, U4).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Requires 1 approval(s); 0 so far"`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(O).
6. nothing written: nothing written.

### AIS-K-07 — a threshold of 2 with one approval: 400 "Requires 2 … 1 so far"
- **Rules:** `confirm_invoice` K3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V, `required_approvals 2`.
4. poappr(O, U4), but approved.
5. poappr(O, U5).
6. poappr(O, U1).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Requires 2 approval(s); 1 so far"`.
4. unchanged: unchanged(V).

### AIS-K-08 — a threshold of 2 with two approvals is met
- **Rules:** `confirm_invoice` K3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V, `required_approvals 2`.
4. poappr(O, U4), but approved.
5. poappr(O, U5), but approved.
6. poappr(O, U1).

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`.

### AIS-K-09 — no approvers and no threshold: 1 approval required
- **Rules:** `confirm_invoice` K3 [BUG-1202]
- **Kind:** bug
- **Expect:** xfail BUG-1202
- **Fails today on:** Then 1 (no error: 0 of 0 counts as met and the invoice is confirmed)

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Requires 1 approval(s); 0 so far"`.
4. unchanged: unchanged(V).
5. nothing written: nothing written.

### AIS-K-10 — sections and approvals both missing: the section text wins
- **Rules:** `confirm_invoice` K2, K3 (order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but of V, `supplier_confirmed True`, `items_confirmed True`.
4. poappr(O, U4).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Confirm supplier, order details, and items before finalizing"`.

### AIS-K-11 — PO checks pass but the invoice is already confirmed: manager 400, PO unchanged
- **Rules:** `confirm_invoice` K7, K1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V.
4. poappr(O, U4), but approved.
5. X (after the commit point).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Invoice is already confirmed"`.
4. session: session clean.
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### AIS-K-12 — the Receiving stage row is missing: 422, the confirm is undone
- **Rules:** `confirm_invoice` K5, K5a, Errors row 6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V, `current_status_id SP1.id`.
4. poappr(O, U4), but approved.
5. `db.delete(SR1)`, then `db.flush()` (`Draft` still exists).
6. X (after the commit point).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Purchase order stage status 'Receiving' not found for this workspace"`.
4. re-read V: `invoice_status == "draft"`.
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### AIS-K-36 — a PO already at Complete stays Complete
- **Rules:** `confirm_invoice` K5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V, `current_status_id SC1.id`.
4. poappr(O, U4), but approved.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read O: `current_status_id == SC1.id`, `invoice_confirmed is True`.
3. committed: `"status_updated" not in types(O)`.
4. committed: `types(O)[-1] == "invoice_confirmed"`.

### AIS-K-37 — no Draft stage row: the stage rows are back-filled and the confirm goes ahead
- **Rules:** `confirm_invoice` K5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V, `current_status_id SP1.id`.
4. poappr(O, U4), but approved.
5. `db.delete(SD1)`, then `db.flush()`.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`.
3. committed: count of `statuses` rows of W1 with `name == "Draft"`: at least 1.
4. committed: re-read O: `db.get(Status, O.current_status_id).name == "Receiving"`.

### AIS-K-13 — a failing notification undoes the whole confirm
- **Rules:** `confirm_invoice` K6; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V.
4. poappr(O, U4), but approved.
5. X (after the commit point).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing notify**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. re-read V: `invoice_status == "draft"`.
3. unchanged: unchanged(O).
4. nothing written: nothing written.
5. committed: x_gone.

### AIS-K-14 — a failing commit saves neither the invoice nor the PO follow-ups
- **Rules:** `confirm_invoice` K5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V.
4. poappr(O, U4), but approved.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read V: `invoice_status == "draft"`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.

### AIS-K-15 — the PO is locked before its approvals are read
- **Rules:** `confirm_invoice` K3a, K3b [BUG-2962]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2962
- **Fails today on:** Then 2 (the PO is read without `FOR UPDATE`)

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. O = po "1", but ready, of V.
4. poappr(O, U4), but approved.
5. `vid = V.id`.
6. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.confirm_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == vid`.
2. statement: row lock on `purchase_orders`, before `purchase_order_approvers`.
3. statement: `"JOIN" not in lock("purchase_orders")`.
4. statement: `lock("account_invoices") is None` or `lock("purchase_orders")` is sent before `lock("account_invoices")`.

### AIS-K-16 — a W0 PO pointing at the invoice is never "the PO's invoice"
- **Rules:** `confirm_invoice` K1; Overview "The PO's invoice"; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. Z0 = po "0" of W0, but `invoice_id V.id`.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`.
3. committed: unchanged(Z0).
4. committed: `types(Z0) == []`.
5. committed: `notes() == []`.

### AIS-K-17 — a W2 PO pointing at the invoice is never "the PO's invoice"
- **Rules:** `confirm_invoice` K1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. Z2 = po "9" of W9, but `invoice_id V.id`.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`.
3. committed: unchanged(Z2).
4. committed: `types(Z2) == []`.

### AIS-K-18 — an expense order's invoice is refused on the invoice page; nobody notified
- **Rules:** `confirm_invoice` K10, K8, Errors row 4 [BUG-2969]
- **Kind:** bug
- **Expect:** xfail BUG-2969
- **Fails today on:** Then 1 (no error: the invoice is confirmed and the expense order's people are notified)

**Given**
1. V = inv.
2. invl(V, "45000.00", 1).
3. E = eo "EXP-2026-009", but of V.
4. eoappr(E, U4).
5. X (after the commit point).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is finalized when expense order EXP-2026-009 is completed."`.
4. re-read V: `invoice_status == "draft"`.
5. count: `IEV(V) == []`.
6. count: `notes() == []`.
7. unchanged: unchanged(E).
8. committed: x_gone.

### AIS-K-19 — a work order's invoice is refused on the invoice page
- **Rules:** `confirm_invoice` K10, Errors row 4 [BUG-2969]
- **Kind:** bug
- **Expect:** xfail BUG-2969
- **Fails today on:** Then 1 (no error: the invoice is confirmed)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. invl(V, "5000.00", 1).
3. WO = wo "WO-2026-031", but of V.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is finalized when work order WO-2026-031 is completed."`.
4. re-read V: `invoice_status == "draft"`.
5. nothing written: nothing written.

### AIS-K-20 — a voided expense order's invoice is refused too
- **Rules:** `confirm_invoice` K10 [BUG-2969]
- **Kind:** bug
- **Expect:** xfail BUG-2969
- **Fails today on:** Then 1 (no error: the invoice is confirmed)

**Given**
1. V = inv.
2. invl(V, "45000.00", 1).
3. E = eo "EXP-2026-009", but of V, `voided True`.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is finalized when expense order EXP-2026-009 is completed."`.
4. re-read V: `invoice_status == "draft"`.

### AIS-K-21 — a soft-deleted work order's invoice is refused too
- **Rules:** `confirm_invoice` K10 [BUG-2969]
- **Kind:** bug
- **Expect:** xfail BUG-2969
- **Fails today on:** Then 1 (no error: the invoice is confirmed)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. invl(V, "5000.00", 1).
3. WO = wo "WO-2026-031", but of V, `is_deleted True`.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is finalized when work order WO-2026-031 is completed."`.
4. re-read V: `invoice_status == "draft"`.

### AIS-K-22 — both an expense and a work order point at it: the expense order is named
- **Rules:** `confirm_invoice` K10 [BUG-2969]
- **Kind:** bug
- **Expect:** xfail BUG-2969
- **Fails today on:** Then 1 (no error: the invoice is confirmed)

**Given**
1. V = inv.
2. invl(V, "45000.00", 1).
3. WO = wo "WO-2026-031", but of V.
4. E = eo "EXP-2026-009", but of V.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is finalized when expense order EXP-2026-009 is completed."`.

### AIS-K-23 — the expense-order refusal comes before the invoice's own status
- **Rules:** `confirm_invoice` K10 (order) [BUG-2969]
- **Kind:** bug
- **Expect:** xfail BUG-2969
- **Fails today on:** Then 3 (today the manager answers "Invoice is already confirmed")

**Given**
1. V = inv, but confirmed.
2. invl(V, "400.00", 1).
3. E = eo "EXP-2026-009", but of V.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This invoice is finalized when expense order EXP-2026-009 is completed."`.

### AIS-K-24 — a W0 expense order pointing at the invoice is not found: it confirms, nobody notified
- **Rules:** `confirm_invoice` K10, K8; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. E0 = eo "EXP-2026-800" of W0, but `invoice_id V.id`.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`.
3. committed: `notes() == []`.
4. committed: unchanged(E0).

### AIS-K-25 — a W2 expense order pointing at the invoice is not found: it confirms, nobody notified
- **Rules:** `confirm_invoice` K10, K8; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv.
2. invl(V, "400.00", 1).
3. E9 = eo "EXP-2026-900" of W9, but `invoice_id V.id`.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`.
3. committed: `notes() == []`.
4. committed: unchanged(E9).

### AIS-K-30 — a sales order's sections not confirmed: 400, nothing written
- **Rules:** `confirm_invoice` K9, Errors row 3 [BUG-2965]
- **Kind:** bug
- **Expect:** xfail BUG-2965
- **Fails today on:** Then 1 (no error: the invoice is confirmed)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. invl(V, "20000.00", 1).
3. S = so "1", but of V, `order_info_confirmed True`.
4. soappr(S, U4), but approved.
5. X (after the commit point).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Confirm order info and items before finalizing"`.
4. re-read V: `invoice_status == "draft"`.
5. unchanged: unchanged(S).
6. nothing written: nothing written.
7. committed: x_gone.

### AIS-K-31 — a sales order's approvals not met: 400 with the counts
- **Rules:** `confirm_invoice` K9 [BUG-2965]
- **Kind:** bug
- **Expect:** xfail BUG-2965
- **Fails today on:** Then 1 (no error: the invoice is confirmed)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. invl(V, "20000.00", 1).
3. S = so "1", but so ready, of V.
4. soappr(S, U4), but approved.
5. soappr(S, U5).

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Requires 2 approval(s); 1 so far"` (only a real read of the two approver rows gives these counts; no read would answer "Requires 1 approval(s); 0 so far").
4. re-read V: `invoice_status == "draft"`.
5. unchanged: unchanged(S).

### AIS-K-32 — the sales checks come before the invoice's own status
- **Rules:** `confirm_invoice` K9 (order) [BUG-2965]
- **Kind:** bug
- **Expect:** xfail BUG-2965
- **Fails today on:** Then 3 (today the manager answers "Invoice is already confirmed")

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`.
2. invl(V, "400.00", 1).
3. S = so "1", but of V.

**When**
- `svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Confirm order info and items before finalizing"`.

### AIS-K-33 — a ready, approved sales order: the order is marked finalized and logs it
- **Rules:** `confirm_invoice` K9 [BUG-2965]
- **Kind:** bug
- **Expect:** xfail BUG-2965
- **Fails today on:** Then 3 (`invoice_confirmed` stays False)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. invl(V, "20000.00", 1).
3. S = so "1", but so ready, of V.
4. soappr(S, U4), but approved.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`.
3. committed: re-read S: `invoice_confirmed is True`, `order_info_confirmed is True`, `items_confirmed is True`.
4. committed: `EV(S)[-1].event_type == "invoice_confirmed"`, `EV(S)[-1].performed_by == U2.id`.
5. committed: `EV(S)[-1].description == f"Invoice #{V.id} confirmed — order locked"`.
6. committed: `EV(S)[-1].metadata_json == {"invoice_id": V.id}`.
7. committed: `types(S) == ["invoice_confirmed"]` (both sections were already set, so no section event; `invoice_confirmed` has no event of its own besides this one).

### AIS-K-34 — a ready, approved sales order's invoice is confirmed at the line sum (today and after the fix)
- **Rules:** `confirm_invoice` K1, K9
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("1.00")`.
2. invl(V, "20000.00", 1).
3. S = so "1", but so ready, of V.
4. soappr(S, U4), but approved.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "confirmed"`, `invoice_amount == Decimal("20000.00")`.
3. committed: `itypes(V) == ["confirmed"]`.

### AIS-K-35 — a ready, approved sales order: its approvers and creator are notified
- **Rules:** `confirm_invoice` K9 [BUG-2965]; `notify_invoice_action` R7a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-2965, BUG-1205
- **Fails today on:** Then 2 (nobody is notified; with only BUG-2965 fixed, only the creator is, until BUG-1205 adds the sales approvers)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. invl(V, "20000.00", 1).
3. S = so "1", but so ready, of V.
4. soappr(S, U4), but approved.

**When**
- `result = svc.confirm_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `recips() == sorted([U1.id, U4.id])`.
3. committed: every row of `notes()`: `entity_type == "sales_order"`, `entity_id == S.id`, `source_id == V.id`, `actor_user_id == U2.id`.
4. committed: every row of `notes()`: `preview == f"confirmed|Invoice confirmed on SO-{S.id} — order locked"`.

### AIS-K-38 — the sales order is locked before its checks
- **Rules:** `confirm_invoice` K9b [BUG-2962]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2962
- **Fails today on:** Then 2 (the sales order is not read `FOR UPDATE`)

**Given**
1. V = inv, but `invoice_type "receivable"`.
2. invl(V, "20000.00", 1).
3. S = so "1", but so ready, of V.
4. soappr(S, U4), but approved.
5. soappr(S, U5), but approved.
6. `vid = V.id`.
7. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.confirm_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == vid`.
2. statement: row lock on `sales_orders`, before `sales_order_approvers`.
3. statement: `"JOIN" not in lock("sales_orders")`.
4. statement: at least one recorded SELECT names `sales_order_approvers` in its `FROM` (the approvals are really read, so Then 2 cannot pass by never reading them).

## `AccountInvoiceService.void_invoice`

### AIS-X-01 — the PO's invoice is voided with its payments and committed
- **Rules:** `void_invoice` X2, X6; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").
3. O = po "1", but locked by V.
4. poline(O, 1).
5. A = poappr(O, U4), but approved.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == V.id`.
3. committed: re-read V: `invoice_status == "voided"`, `void_note == "Wrong amount"`, `paid_amount == Decimal("0.00")`.
4. committed: re-read P: `is_voided is True`, `voided_by == U2.id`.

### AIS-X-02 — the PO's invoice: approvals reset, PO unlinked, supplier and items unconfirmed, stage re-derived
- **Rules:** `void_invoice` X3, X4, X5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V, `paid True`.
3. poline(O, 1).
4. A = poappr(O, U4), but approved.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read A: `approved is False`, `approved_at is None`.
3. committed: re-read O: `invoice_id is None`, `invoice_confirmed is False`, `paid is False`.
4. committed: re-read O: `supplier_confirmed is False`, `items_confirmed is False`, `details_confirmed is True`.
5. committed: re-read O: `current_status_id == SP1.id`.
6. committed: `types(O) == ["approvals_reset", "invoice_voided", "supplier_unconfirmed", "items_unconfirmed", "status_updated"]`.
7. committed: `EV(O)[0].description == "Cleared approvals after invoice voided (1 approval(s) cleared)"`.

### AIS-X-03 — the PO's "invoice voided" event carries the void reason
- **Rules:** `void_invoice` X4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V.
3. poline(O, 1).

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. event: `types(O)[0] == "invoice_voided"`.
3. event: `EV(O)[0].description == f"Invoice #{V.id} voided"`, `EV(O)[0].performed_by == U2.id`.
4. event: `EV(O)[0].metadata_json == {"invoice_id": V.id, "changes": [{"field": "void_note", "label": "Void reason", "from_value": None, "to_value": "Wrong amount"}]}`.

### AIS-X-04 — goods received on a PO line: 400, nothing written
- **Rules:** `void_invoice` X1, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").
3. O = po "1", but locked by V.
4. poline(O, 1).
5. poline(O, 2), but `quantity_received Decimal("0.01")`.
6. A = poappr(O, U4), but approved.
7. X (after the commit point).

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == RECVD`.
4. session: session clean.
5. unchanged: unchanged(V).
6. unchanged: unchanged(P).
7. unchanged: unchanged(O).
8. unchanged: unchanged(A).
9. nothing written: nothing written.
10. committed: x_gone.

### AIS-X-05 — the received-goods check runs before the manager's checks
- **Rules:** `void_invoice` X1 (order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv.
2. O = po "1", but ready, of V.
3. poline(O, 1), but `quantity_received Decimal("5.00")`.

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == RECVD`.
4. unchanged: unchanged(V).

### AIS-X-06 — a received line of another workspace on the PO does not block
- **Rules:** `void_invoice` X1 (lines of the workspace); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V.
3. poline(O, 1).
4. poline(O, 2), but `workspace_id W2.id`, `quantity_received Decimal("5.00")`.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "voided"`.

### AIS-X-07 — no approver approved: no approvals_reset event
- **Rules:** `void_invoice` X3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V.
3. poline(O, 1).
4. A = poappr(O, U4).

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: `"approvals_reset" not in types(O)`.
3. committed: `types(O)[0] == "invoice_voided"`.
4. committed: unchanged(A).

### AIS-X-08 — the PO is locked before its lines are read
- **Rules:** `void_invoice` X1, X1c [BUG-2962]; K3b; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2962
- **Fails today on:** Then 2 (the PO is read without `FOR UPDATE`)

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V.
3. poline(O, 1).
4. `vid = V.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.void_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == vid`.
2. statement: row lock on `purchase_orders`, before `purchase_order_items`.
3. statement: line lock on `purchase_order_items`.
4. statement: `lock("account_invoices") is None` or `lock("purchase_order_items")` is sent before `lock("account_invoices")` (lock order: order row, then lines, then invoice).

### AIS-X-09 — a missing stage row: 422, none of the void is saved
- **Rules:** `void_invoice` X6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").
3. O = po "1", but locked by V.
4. poline(O, 1).
5. A = poappr(O, U4), but approved.
6. `O.current_status_id = SD1.id`, then `db.flush()`.
7. `db.delete(SP1)`, `db.delete(SR1)`, `db.delete(SC1)`, then `db.flush()`.
8. X (after the commit point).

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. unchanged: unchanged(V).
4. unchanged: unchanged(P).
5. unchanged: unchanged(O).
6. unchanged: unchanged(A).
7. nothing written: nothing written.
8. committed: x_gone.

### AIS-X-10 — a failing commit saves none of the void
- **Rules:** `void_invoice` X6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. O = po "1", but locked by V.
3. poline(O, 1).
4. A = poappr(O, U4), but approved.

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read V: `invoice_status == "confirmed"`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(A).
6. nothing written: nothing written.

### AIS-X-11 — a manual invoice: only the invoice and its payments are voided
- **Rules:** `void_invoice` X7, X2
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Entered twice")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "voided"`, `void_note == "Entered twice"`.
3. committed: re-read P: `is_voided is True`.
4. committed: count of `purchase_order_events`, `sales_order_events`, `expense_order_events`, `work_order_events` rows (all workspaces): exactly 0.

### AIS-X-12 — a draft invoice: the manager's 400 passes unchanged, nothing saved
- **Rules:** `void_invoice` X2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. V = inv.
2. P = pay(V, "100.00").
3. X (after the commit point).

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Draft invoices cannot be voided — delete them instead"`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(P).
6. nothing written: nothing written.
7. committed: x_gone.

### AIS-X-13 — a completed sales order's invoice is frozen; payments kept
- **Rules:** `void_invoice` X2 [BUG-2731]
- **Kind:** bug
- **Expect:** xfail BUG-2731
- **Fails today on:** Then 1 (no error: the invoice and its payments are voided)

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").
3. S = so "1", but finalized by V, `order_completed True`.

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == LOCK("sales order")`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(P).

### AIS-X-14 — a credit note of a pending return: the return is voided with it
- **Rules:** `void_invoice` X2 [BUG-2788]
- **Kind:** bug
- **Expect:** xfail BUG-2788
- **Fails today on:** Then 3 (the return stays "pending")

**Given**
1. O = po "1", but ready.
2. CN = inv, but confirmed, `invoice_type "receivable"`, `order_type "purchase_order"`, `order_id O.id`.
3. R = `PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O.id, return_number=f"PR-{TAG}-1", return_type="refund", created_by=U1.id, invoice_id=CN.id)`.

**When**
- `result = svc.void_invoice(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id, void_note="Return cancelled")`.

**Then**
1. returns: `result.id == CN.id`.
2. committed: re-read CN: `invoice_status == "voided"`.
3. committed: re-read R: `status == "voided"`.

### AIS-X-15 — goods delivered on a sales order: 400, payments kept
- **Rules:** `void_invoice` X1a, Errors row 2 [BUG-2967]
- **Kind:** bug
- **Expect:** xfail BUG-2967
- **Fails today on:** Then 1 (no error: the invoice and its payment are voided)

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`, `invoice_amount Decimal("20000.00")`, `paid_amount Decimal("8000.00")`, `payment_status "partial"`.
2. P = pay(V, "8000.00").
3. S = so "1", but finalized by V.
4. soline(S), but `quantity_delivered Decimal("4.00")`.
5. X (after the commit point).

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void invoice after delivery has been recorded on the linked order"`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(P).
6. unchanged: unchanged(S).
7. nothing written: nothing written.
8. committed: x_gone.

### AIS-X-16 — nothing delivered on the sales order: the void goes ahead
- **Rules:** `void_invoice` X1a (other side), X2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`.
2. S = so "1", but finalized by V.
3. soline(S).

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "voided"`.

### AIS-X-17 — a sales order is released after its invoice is voided
- **Rules:** `void_invoice` X8 [BUG-2966]
- **Kind:** bug
- **Expect:** xfail BUG-2966
- **Fails today on:** Then 2 (the sales order is not touched)

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`.
2. S = so "1", but finalized by V, `paid True`.
3. soline(S).
4. A = soappr(S, U4), but approved.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read S: `invoice_id is None`, `invoice_confirmed is False`, `is_invoiced is False`, `paid is False`.
3. committed: re-read S: `order_info_confirmed is False`, `items_confirmed is False`.
4. committed: re-read A: `approved is False`, `approved_at is None`.
5. committed: `"invoice_voided" in types(S)`.
6. committed: the `invoice_voided` row of `EV(S)`: `description == f"Invoice #{V.id} voided"`, `performed_by == U2.id`.
7. committed: its `metadata_json == {"invoice_id": V.id, "changes": [{"field": "void_note", "label": "Void reason", "from_value": None, "to_value": "Wrong amount"}]}`.

### AIS-X-18 — an expense order is released after its invoice is voided; approvals kept
- **Rules:** `void_invoice` X8 [BUG-2966]
- **Kind:** bug
- **Expect:** xfail BUG-2966
- **Fails today on:** Then 2 (the expense order still points at the voided invoice)

**Given**
1. V = inv, but confirmed.
2. E = eo "EXP-2026-007", but of V.
3. A = eoappr(E, U4), but approved.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Fix amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read E: `invoice_id is None`.
3. committed: `types(E) == ["invoice_voided"]`.
4. committed: `EV(E)[0].description == f"Invoice #{V.id} voided"`, `EV(E)[0].performed_by == U2.id`.
5. committed: unchanged(A).

### AIS-X-19 — an expense order's invoice is voided and its approvals stay (today and after the fix)
- **Rules:** `void_invoice` X8 (approvals unchanged), X2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. E = eo "EXP-2026-007", but of V.
3. A = eoappr(E, U4), but approved.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Fix amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "voided"`.
3. committed: unchanged(A).

### AIS-X-20 — a work order is released after its invoice is voided
- **Rules:** `void_invoice` X8 [BUG-2966]
- **Kind:** bug
- **Expect:** xfail BUG-2966
- **Fails today on:** Then 2 (the work order still points at the voided invoice)

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`.
2. WO = wo "WO-2026-031", but of V.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Fix amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read WO: `invoice_id is None`.
3. committed: `types(WO) == ["invoice_voided"]`.
4. committed: `EV(WO)[0].description == f"Invoice #{V.id} voided"`, `EV(WO)[0].performed_by == U2.id`.

### AIS-X-21 — another workspace's sales order pointing at the invoice is not touched
- **Rules:** `void_invoice` X8 (orders of the workspace only); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`.
2. S9 = so "9" of W9, but finalized by V, `current_status_id SD9.id`.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "voided"`.
3. committed: unchanged(S9).
4. committed: `types(S9) == []`.

### AIS-X-22 — a blank void note is rejected by the schema
- **Rules:** `void_invoice` Errors row 3 [BUG-626]
- **Kind:** bug
- **Expect:** xfail BUG-626
- **Fails today on:** Then 1 (no error: the blank note is accepted)

**Given**
1. Standing rows only.

**When**
- build `VoidInvoiceRequest(void_note="   ")` (target `schema`; `svc` is not called).

**Then**
1. raises: `pydantic.ValidationError`.

### AIS-X-23 — a service line fulfilled without any delivery also blocks the void
- **Rules:** `void_invoice` X1a, X1b [BUG-2967]
- **Kind:** bug
- **Expect:** xfail BUG-2967
- **Fails today on:** Then 1 (no error: the invoice and its payment are voided)

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").
3. S = so "1", but finalized by V.
4. soline(S), but `requires_delivery False`, `quantity_ordered Decimal("1.00")`, `quantity_delivered Decimal("1.00")`, `unit_price Decimal("400.00")`, `line_total Decimal("400.00")`.

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void invoice after delivery has been recorded on the linked order"`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(P).

### AIS-X-24 — a line delivered and then fully returned still blocks the void
- **Rules:** `void_invoice` X1a, X1b [BUG-2967]
- **Kind:** bug
- **Expect:** xfail BUG-2967
- **Fails today on:** Then 1 (no error: the invoice is voided)

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`.
2. S = so "1", but finalized by V.
3. soline(S), but `quantity_delivered Decimal("4.00")`, `quantity_returned Decimal("4.00")`.

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void invoice after delivery has been recorded on the linked order"`.
4. unchanged: unchanged(V).

### AIS-X-25 — the sales order row, then its lines, are locked before the delivered check
- **Rules:** `void_invoice` X1a, X1c [BUG-2962]; K9b; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2962
- **Fails today on:** Then 2 (the sales order is not read `FOR UPDATE`)

**Given**
1. V = inv, but confirmed, `invoice_type "receivable"`.
2. S = so "1", but finalized by V.
3. soline(S).
4. `vid = V.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.void_invoice(db, invoice_id=vid, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == vid`.
2. statement: row lock on `sales_orders`, before `sales_order_items`.
3. statement: line lock on `sales_order_items`.
4. statement: `lock("account_invoices") is None` or `lock("sales_order_items")` is sent before `lock("account_invoices")`.

### AIS-X-26 — a non-HTTP error after the first writes is rolled back and passes unchanged
- **Rules:** `void_invoice` X6; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. V = inv, but confirmed, `paid_amount Decimal("100.00")`, `payment_status "partial"`.
2. P = pay(V, "100.00").
3. O = po "1", but locked by V.
4. poline(O, 1).
5. A = poappr(O, U4), but approved.
6. X (after the commit point).

**When**
- `svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`, inside **failing unconfirm**.

**Then**
1. raises: `exc.value is E`.
2. mock called: `rb.call_count >= 1`.
3. session: `X not in db` (checked right after the call).
4. unchanged: unchanged(V).
5. unchanged: unchanged(P).
6. unchanged: unchanged(O).
7. unchanged: unchanged(A).
8. nothing written: nothing written.
9. committed: x_gone.

### AIS-X-27 — a W0 PO pointing at the invoice is not "the PO's invoice": its received line does not block, it is not touched
- **Rules:** `void_invoice` X1, X7; Overview "The PO's invoice"; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. Z0 = po "0" of W0, but ready, `invoice_id V.id`, `invoice_ever_linked True`, `invoice_confirmed True`.
3. poline(Z0, 1), but `quantity_received Decimal("5.00")`.
4. ZA = poappr(Z0, U3), but approved.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "voided"`.
3. committed: unchanged(Z0).
4. committed: unchanged(ZA).
5. committed: `types(Z0) == []`.

### AIS-X-28 — a W2 PO pointing at the invoice is not "the PO's invoice": its received line does not block, it is not touched
- **Rules:** `void_invoice` X1, X7; Overview "The PO's invoice"; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V = inv, but confirmed.
2. Z2 = po "9" of W9, but ready, `invoice_id V.id`, `invoice_ever_linked True`, `invoice_confirmed True`.
3. poline(Z2, 1), but `quantity_received Decimal("5.00")`.
4. ZA = poappr(Z2, U3), but approved.

**When**
- `result = svc.void_invoice(db, invoice_id=V.id, workspace_id=W1.id, user_id=U2.id, void_note="Wrong amount")`.

**Then**
1. returns: `result.id == V.id`.
2. committed: re-read V: `invoice_status == "voided"`.
3. committed: unchanged(Z2).
4. committed: unchanged(ZA).
5. committed: `types(Z2) == []`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| C1, U1, V1, L1 details (R1–R15, filters, ordering, money) | `account_invoice_manager.cases.md` | every manager rule; here only one pass-through per path |
| K9 "the order's own Finalize invoice then answers 409 `Invoice is already finalized`" | `SalesService` (sales order finalize) | after an invoice-page confirm, the sales order's finalize gives 409 |
| K8 expense-order notification on completion | `expense_order_service` | approvers and creator notified when the order completes |
| Work order FU-1 (voided / completed order can get an invoice; void leaves a hand-confirmed invoice payable) | `work_order_service` | per `work_order_manager.spec.md` FU-1 |
| BUG-2734 (completed / received PO cannot be voided) | `purchase_order_service` | PO void refusal |
| BUG-2962 concurrency (two sessions racing confirm / void / resync) | integration tests | the loser sees the new state and gets the normal error; unit cards only check the `FOR UPDATE` read |
| `void_note` blank → 422 at the endpoint (BUG-626) | `POST /invoices/{id}/void` | 422 body |
| Permission checks (any member can finalize / void / delete) | `docs/future/permissions.md` | not a rule today |
| `list_accounts_hub_page` (dead code, Q8) | dead-code checklist | removal |

## Spec gaps
None open. All eight gaps of revision 1 were closed by the spec's Gap log (fill-gaps 2026-11-21):

| # | Resolved by | How the cases use it |
|---|---|---|
| 1 | G1 / L1a: every read's parameter names and defaults | L-01 … L-18 use those keywords; L-11 calls the manager by keyword; new L-16 (`prioritize_purchase_order_id`), L-17, L-18 (filters forwarded) |
| 2 | G2 / K5a: confirm moves the PO to `Receiving`, `Complete` stays; 422 names `Receiving` only when `Draft` exists | K-02 expects SR1; K-12 checks the exact 422 text; new K-36, K-37 |
| 3 | G3 / S6b: expense-line nullability and fallbacks, `source_order_item_id` = line id | S-14 checks `source_order_item_id`; new S-28 |
| 4 | G4 / X1b: `quantity_delivered` covers direct fulfilment; returns not subtracted | new X-23, X-24 |
| 5 | G5 / K9: preview `Invoice confirmed on SO-<id> — order locked` | K-35 Then 4 |
| 6 | G6 / S1a, K3b, K9b, X1c: exact lock clauses and lock order | Conventions "row lock" / "line lock"; S-25, K-15, X-08 pinned; new K-38, X-25 |
| 7 | G7 / S5: the `Item <item_id>` fallback is unreachable | no case (nothing to test) |
| 8 | G8 / K9a: sales section events | K-33 Then 7 (no section events when both are already set); the section branches are unreachable through K9 |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_invoice` | C1 | AIS-C-01, C-05, C-06 |
| `create_invoice` | C2 | AIS-C-02, C-03, C-04 |
| `get_invoice` | G1 | AIS-G-01 … G-04 |
| reads | L1 | AIS-L-01 … L-06, L-10 … L-17 |
| reads | L1a | AIS-L-11, L-16, L-17, L-18 |
| reads | L2 | AIS-L-07, L-08, L-09, L-18 |
| reads | L3 (TC6) | AIS-L-01, L-05, L-07, L-10, L-11, L-13, G-01, G-04 |
| `update_invoice` | U1 | AIS-U-01, U-02, U-03, U-04, U-05 |
| `update_invoice` | U2 | AIS-U-01, U-02 |
| `delete_invoice` | D1 / Errors 1–4 | AIS-D-05, D-06, D-07, D-08, D-09, D-17, D-18 |
| `delete_invoice` | D2 | AIS-D-01, D-15, D-16 |
| `delete_invoice` | D3 | AIS-D-01, D-02 |
| `delete_invoice` | D4 | AIS-D-03, D-16, D-17, D-18 |
| `delete_invoice` | D4a [BUG-2968] | AIS-D-04 |
| `delete_invoice` | D5 [BUG-2732] | AIS-D-10, D-11, D-12 (xfail); D-13, D-14 (pass) |
| `delete_invoice` | D6 | AIS-D-01, D-17, D-18 |
| `revert_to_draft` | V1 | AIS-V-01, V-02, V-03, V-04 [BUG-2736], V-05 [BUG-2730], V-06 [BUG-2733], V-07 |
| `revert_to_draft` | V2 | AIS-V-01 |
| `resync_items` | S1 / Errors 1 | AIS-S-27 |
| `resync_items` | S1, S1a [BUG-2962] | AIS-S-25 |
| `resync_items` | S2 | AIS-S-07, S-08, S-09 |
| `resync_items` | S3 | AIS-S-10 … S-13 |
| `resync_items` | S4 | AIS-S-01, S-14, S-26, S-29 |
| `resync_items` | S5 / Errors 4, 7 | AIS-S-01 … S-06 (the `Item <item_id>` fallback is unreachable, G7) |
| `resync_items` | S6 / Errors 4 | AIS-S-14, S-15, S-16, S-28 |
| `resync_items` | S6b | AIS-S-14, S-28 |
| `resync_items` | S6a [BUG-2963] / Errors 5 | AIS-S-17, S-18, S-19 |
| `resync_items` | S7 [BUG-2964] / Errors 5 | AIS-S-20 … S-23 |
| `resync_items` | S8 [BUG-2964] / Errors 6 | AIS-S-24 |
| `confirm_invoice` | K1 | AIS-K-01, K-11, K-16, K-17, K-34 |
| `confirm_invoice` | K2 / Errors 1 | AIS-K-04, K-05, K-10 |
| `confirm_invoice` | K3 / Errors 2 | AIS-K-06, K-07, K-08, K-09 [BUG-1202], K-10 |
| `confirm_invoice` | K3a, K3b [BUG-2962] | AIS-K-15 (and X-08 for the PO read of X1) |
| `confirm_invoice` | K4 | AIS-K-01, K-02, K-34 |
| `confirm_invoice` | K5 / Errors 6 | AIS-K-02, K-12, K-14 |
| `confirm_invoice` | K5a | AIS-K-02, K-12, K-36, K-37 |
| `confirm_invoice` | K6 | AIS-K-03, K-13 |
| `confirm_invoice` | K7 | AIS-K-11 |
| `confirm_invoice` | K8 [BUG-2969] | AIS-K-18 (xfail); K-24, K-25 (pass) |
| `confirm_invoice` | K9 [BUG-2965] / Errors 3 | AIS-K-30 … K-33, K-35 (K-35 also BUG-1205) (xfail); K-34 (pass) |
| `confirm_invoice` | K9a [BUG-2965] | AIS-K-33 |
| `confirm_invoice` | K9b [BUG-2962] | AIS-K-38, X-25 |
| `confirm_invoice` | K10 [BUG-2969] / Errors 4 | AIS-K-18 … K-23 (xfail); K-24, K-25 (pass) |
| `void_invoice` | X1 / Errors 1 | AIS-X-04, X-05, X-06, X-27, X-28 |
| `void_invoice` | X1, X1c [BUG-2962] | AIS-X-08, X-25 |
| `void_invoice` | X1a [BUG-2967] / Errors 2 | AIS-X-15, X-23, X-24 (xfail); X-16 (pass) |
| `void_invoice` | X1b | AIS-X-23, X-24 |
| `void_invoice` | X2 / Errors 4 | AIS-X-01, X-11, X-12, X-13 [BUG-2731], X-14 [BUG-2788] |
| `void_invoice` | X3 | AIS-X-02, X-07 |
| `void_invoice` | X4 | AIS-X-02, X-03 |
| `void_invoice` | X5 | AIS-X-02 |
| `void_invoice` | X6 | AIS-X-01, X-09, X-10, X-26 |
| `void_invoice` | X7 | AIS-X-11, X-27, X-28 |
| `void_invoice` | X8 [BUG-2966] | AIS-X-17, X-18, X-20 (xfail); X-19, X-21 (pass) |
| `void_invoice` | Errors 3 [BUG-626] | AIS-X-22 (schema) |
| all writes | TC1 | AIS-C-01, U-01, U-05, D-01, D-16, V-01, S-01, S-29, K-01, K-02, X-01 |
| all writes | TC2 | AIS-C-01, U-01, V-01, S-01, K-01, X-01 (delete: not applicable, D-02) |
| all writes | TC3 | AIS-C-02, C-03, U-03, D-05, D-08, V-02, S-03, S-06, K-04, K-11, K-12, K-13, X-04, X-09, X-12, X-26 |
| all writes | TC4 | AIS-C-05, U-04, D-15, S-26, K-14, X-10 |
| all writes | TC5 | AIS-C-06 |
