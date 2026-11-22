# Test cases — `app/services/orders_overview_service.py`

> **Spec:** `tests/unit/services/orders_overview_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 (2026-11-10) — `orders_overview_service.verify.md` findings 1–8, 10, 11 and spec round 4 (R8c). New pass cards: TI-18, TI-19 (name and unit of items seen only on transfer / sales lines, empty name falls back; F1), TV-14 (sales never in vendors; F2), TV-15 (deleted account keeps its PO vendor row; F3), TV-16 (expense-only vendor, empty name; F4), FP-10, FT-08 (project of another factory dropped under both readings; F5), FP-11, FT-09 (storage id equal to a project and component id of the factory; F6), TF-36 (source machine fallback; F7), TI-21, TF-35, TV-17, TC-08 (0.10 + 0.20 exact sums; F8), TI-20 (R8c: empty unit gives `item_unit` None on every line kind). F10: spec gap 1 closed by `_build_top_factories` R8b; FV-08, FV-09 now cite R8b (expectation unchanged: every list empty). F11: OQ29-06, 07, 12, 13, 16, 17 and OQ30-08 Expect lines name every bug they need. No card retired.
> **Revision:** 3 (2026-11-10) — coordinator follow-up: new FV-08 (factory view on W2's factory F9) and FV-09 (on W0's F0): W1 orders linking that factory and that workspace's own orders show in no list (HR-16); strict xfail BUG-2502 + BUG-2504 (today any `factory_id` raises). Parallel runs: the per-process number suffix **GN** the executor already used is now stated in Conventions. New spec gap 1 (the factory view's answer for another workspace's `factory_id` is not written in the spec). No card retired.
> **Revision:** 2 (2026-11-10) — spec round 2: owner answers OQ-29 → BUG-2480 (committed / projected / total, Money stage D1–D8) and OQ-30 → BUG-2481 (split: purchase spend, `sales_revenue`, work cost; items ranked by purchased quantity); gaps G1–G7 filled. Changed: Conventions (line builders pass `workspace_id` (G1); `fmap` (G2); stage statuses SR / SC / SP, U2 and approver builders (D3–D7); real soft-delete columns on FD and accounts (G5); method kinds (G7); the OQ isolation note replaced by the stage note), OOV-IR-01 (PO `order_date`, G6), OOV-AF-01 … AF-03 (`fmap`, entry values), OOV-TF-06, OOV-TF-07, OOV-TI-05 (the sales / work money moved to xfail cards OQ30-11 … OQ30-13), OOV-TF-21, OOV-TF-22 (no `total_value`: it becomes purchase spend), OOV-TV-04, OOV-TC-02 (deleted account columns), OOV-TF-33, OOV-TI-16, OOV-TV-12 (now strict: tied rows come from different queries, so today's order is fixed; G4), OOV-OQ29-01 … 04 (no `Pending:` line; still pass, they hold after BUG-2480; OQ29-04 compares a set of factories), OOV-OQ30-01 … 03 (now strict xfail BUG-2481), OOV-OQ30-04 (no `Pending:` line; still pass). New: OOV-AF-04 … AF-07, OOV-GS-15, OOV-TF-34, OOV-TI-17, OOV-TV-13 (tie on name, id step), OOV-TC-07, OOV-TE-06 (strict ORDER BY alarms, SQL cuts), OOV-OQ29-05 … OQ29-17 (BUG-2480), OOV-OQ30-05 … OQ30-13 (BUG-2481). No card retired.
> **Counts:** 180 cases · 110 expected-to-pass · 70 expected-to-fail (bugs; 2 non-strict) · 3 deferred

## Reviewer summary
- **Per callable:** `_dec` 6 · `_po_report_date` 2 · `_in_date_range` 3 · `_filter_po_by_factory` 11 (3 bug) · `_filter_transfer_by_factory` 9 (2 bug) · `_accumulate_factory` 7 · `_build_top_factories` 36 (16 bug) · `get_stats` general 15 · top items 21 (6 bug) · top vendors 17 (6 bug) · top customers 8 (3 bug) · top categories 6 (3 bug) · factory view 9 (9 bug) · OQ-29 / BUG-2480 17 (12 bug) · OQ-30 / BUG-2481 13 (10 bug).
- **Depth:** full (skill step 1a): money totals and order counting. Full depth on workspace isolation (W0 and W2 orders of every kind on both sides of W1, W2 orders that link to W1 rows, one card per cross-workspace link shape for BUG-2504, approver rows of W0 / W2 on a W1 order), voided and deleted orders (one card per kind and list, and "in none of committed / projected / total" per measure), exact money (`Decimal` literals and `str()` scale; nothing is rounded here, so there is no half-up card), every leaderboard's sort keys, cut and ties down to the id step, and the report-day window of every order query at both edges.
- **Owner answers (2026-11-10):** OQ-29 → BUG-2480: each money measure (item purchase spend, item sales revenue, vendor, customer and category spend, factory purchase spend / sales revenue / work cost) gets one card splitting it across every committed and projected path of D3–D7, and one card with voided (and deleted) orders in none of the three. The old OQ-29 cards still hold after the fix (drafts still count in the total and in counts) and stay pass. OQ-30 → BUG-2481: the old OQ-30 cards that state today's mixing are now strict xfail; the parts that hold after the fix (quantities and counts add every kind) are pass cards OQ30-04 … 06.
- **Expected-to-fail:** BUG-2480 12, BUG-2481 10, BUG-2500 6, BUG-2501 1, BUG-2502 7, BUG-2502 + BUG-2504 2 (FV-08, FV-09, R8b), BUG-2503 6, BUG-2504 15, BUG-2505 10 (2 non-strict), BUG-2506 1. All strict except TC-06, TE-05.
- **Notable design choices:**
  - Stage paths are built without `required_approvals` on PO, sales and work orders (the spec names that column for expense orders only): committed through a stage (PO status `Receiving` / `Complete`, `order_completed`, `completed_at`, work `IN_PROGRESS` / `COMPLETED`) or through approver rows all approved; projected through no approver rows ("at least 1"), or one of two approved.
  - The standing status S1 "Approved" is not a PO stage name: after BUG-2480 an S1 PO with no approvers is projected. Cards outside the OQ-29 section read totals and counts only, which do not depend on that.
  - Python-sorted ties (items, vendors, factories) are strict now: each tied row comes from a different query (PO → transfer → sales → work; PO vendors before expense-only vendors), so today's first-seen order is fixed and always differs from the name / id order. SQL-cut ties (customers, categories) keep their non-strict order cards plus one strict "ORDER BY has the tie term" alarm each.
  - BUG-2480 / BUG-2481 cards use the new field names the spec gives (`total_spend_committed`, `sales_revenue`, `purchase_spend`, `work_cost` …); they fail today on the first such field.
  - Cards that need more than one fix name every bug on the Expect line (OQ29-06, 07, 12, 13, 16, 17, OQ30-08, FV-08, FV-09); the marker reason lists them all.
  - Exactness cards TI-21, TF-35, TV-17, TC-08 add 0.10 + 0.20 (a float sum gives 0.30000000000000004); nothing in this module rounds, so no half-up card.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `OOV` = `app/services/orders_overview_service.py`. `D` _dec · `RD` _po_report_date · `IR` _in_date_range · `FP` _filter_po_by_factory · `FT` _filter_transfer_by_factory · `AF` _accumulate_factory · `TF` _build_top_factories · `GS` get_stats (limit, workspace, session) · `TI` top items · `TV` top vendors · `TC` top customers · `TE` top expense categories · `FV` get_stats with `factory_id` · `OQ29` = committed / projected split (BUG-2480) · `OQ30` = purchase / sales / work split (BUG-2481).

**Imports.** `from app.services.orders_overview_service import OrdersOverviewService, orders_overview_service, _dec`; `OrdersOverviewStatsResponse`, `TopFactoryRow` (`app.schemas.orders_overview`). Models from `app.models.<module>`: `factory.Factory`, `machine.Machine`, `project.Project`, `project_component.ProjectComponent`, `status.Status`, `account.Account`, `item.Item`, `work_order_type.WorkOrderType`, `purchase_order.PurchaseOrder`, `purchase_order_item.PurchaseOrderItem`, `transfer_order.TransferOrder`, `transfer_order_item.TransferOrderItem`, `sales_order.SalesOrder`, `sales_order_item.SalesOrderItem`, `expense_order.ExpenseOrder`, `work_order.WorkOrder`, `purchase_order_approver.PurchaseOrderApprover`, `sales_order_approver.SalesOrderApprover`, `expense_order_approver.ExpenseOrderApprover`, `work_order_approver.WorkOrderApprover`; `WorkOrderStatusEnum` (`app.models.enums`). `InvalidRequestError` (`sqlalchemy.exc`); `InvalidOperation`, `Decimal` (`decimal`); `defaultdict` (`collections`); `date`, `datetime`; `patch`; `event` (`sqlalchemy`); `os`.

**Fixed values.** `svc` = `orders_overview_service`. START = `date(2026, 5, 1)`, END = `date(2026, 5, 31)`, PRE = `date(2026, 4, 30)`, POST = `date(2026, 6, 1)`, MID = `date(2026, 5, 10)`. MIDT = `datetime(2026, 5, 10, 12, 0, 0)`. PRE_LAST = `datetime(2026, 4, 30, 23, 59, 59, 999999)`, START_0 = `datetime(2026, 5, 1, 0, 0, 0)`, END_LAST = `datetime(2026, 5, 31, 23, 59, 59, 999999)`, POST_0 = `datetime(2026, 6, 1, 0, 0, 0)`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. MISSING = `999999999`. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k` (an explicit row id; a row written "`id XID(k)`" passes `id=XID(k)`). `result` = what the When returns.

**Calls.** `svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)` unless the card says otherwise. `svc._build_top_factories(db, W1.id, START, END, 10)` (positional). Helpers are called on `svc` (`_factory_from_location` is a static method, the others instance methods; `_dec` is a module function). **poq** = `db.query(PurchaseOrder.id).filter(PurchaseOrder.workspace_id == W1.id)`; **toq** = `db.query(TransferOrder.id).filter(TransferOrder.workspace_id == W1.id)`. **fmap()** = `defaultdict(lambda: {"order_count": 0, "total_value": Decimal(0), "purchase_count": 0, "transfer_count": 0, "sales_count": 0, "work_count": 0})`.

**Standing rows** (every test, no Given line; built in this order, each flushed, so within each table W0 rows < W1 rows < W2 rows): W0, W1, W2 = `make_workspace(db)`; U1, U2 = `make_profile(db)`.
- W0: S0 = `Status(workspace_id=W0.id, name="Approved", comment="Stage")`; F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`; M0 = `Machine(workspace_id=W0.id, factory_id=F0.id, name="Zero Press")`; WT0 = `WorkOrderType(workspace_id=W0.id, name="Repair")`; AC0 = `Account(workspace_id=W0.id, name="Zero Co")`; I0 = `Item(workspace_id=W0.id, name="Zero Bolt", name_normalized="zero bolt", unit="pcs")`.
- W1: S1 = Status "Approved" in W1; SD = Status `name "Draft"` in W1; SP = `"Planning"`, SR = `"Receiving"`, SC = `"Complete"` (each a Status in W1, `comment "Stage"`). Factories in this order: FA `"Alpha Works"`/`"FA"`, F1 `"Factory One"`/`"F1"`, F2 `"Factory Two"`/`"F2"`, FD `"Old Plant"`/`"OP"` with `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`, FI `"Idle Plant"`/`"IP"` with `is_active False` (so `FA.id < F1.id < F2.id`). Machines: MA (FA, `"Press A"`), M1 (F1, `"Press 1"`), M2 (F2, `"Press 2"`), MI (F1, `"Idle Press"`, `is_active False`). WT1 = WorkOrderType "Repair" in W1. Accounts: AC1 `"Acme"`, AC2 `"Beta"`, AC3 `"Cargo"`. Items (unit `"pcs"`, `name_normalized` = name lower case): I1 `"Bolt"`, I2 `"Nut"`, I3 `"Washer"`. PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Plant Upgrade", description="Main")`.
- W2: S9, F9 `"Factory Nine"`/`"F9"`, M9 (F9, `"Far Press"`), WT9, AC9 `"Far Co"`, I9 `"Far Crate"` — the W0 shapes with W2.
- A **deleted account** (built in a card) = `Account(workspace_id=W1.id, name=…, is_deleted=True, is_active=False, deleted_at=T0, deleted_by=U1.id)`.

**Order builders** (W1 by default; flushed one at a time in the order written; the card lists after "but" every column that differs).
- **po** = `PurchaseOrder(workspace_id=W1.id, po_number=…, destination_type="storage", destination_id=F1.id, order_date=MID, total_amount=Decimal("10.00"), current_status_id=S1.id, created_by=U1.id)`. **pol(p, I, q, sub)** = `PurchaseOrderItem(workspace_id=p.workspace_id, purchase_order_id=p.id, line_number=1, item_id=I.id, quantity_ordered=q, line_subtotal=sub)` (a second line on one order: `line_number 2`).
- **to** = `TransferOrder(workspace_id=W1.id, transfer_number=GN(…), source_location_type="storage", source_location_id=F2.id, destination_location_type="storage", destination_location_id=F1.id, current_status_id=S1.id, created_by=U1.id, created_at=MIDT)`. **tol(t, I, q)** = `TransferOrderItem(workspace_id=t.workspace_id, transfer_order_id=t.id, line_number=1, item_id=I.id, quantity=q)`.
- **so** = `SalesOrder(workspace_id=W1.id, sales_order_number=GN(…), account_id=AC1.id, factory_id=F1.id, order_date=MID, total_amount=Decimal("10.00"), current_status_id=S1.id, created_by=U1.id)`. **sol(s, I, q, lt)** = `SalesOrderItem(workspace_id=s.workspace_id, sales_order_id=s.id, item_id=I.id, description="Line", quantity_ordered=q, unit_price=Decimal("1.00"), line_total=lt)`; a **free-text** line has `item_id=None`.
- **eo** = `ExpenseOrder(workspace_id=W1.id, expense_number=…, expense_category="other", expense_date=MID, subtotal=Decimal("0.00"), total_amount=Decimal("10.00"), created_by=U1.id)` (`account_id` not passed).
- **wo** = `WorkOrder(workspace_id=W1.id, work_order_number=…, work_order_type_id=WT1.id, title="Fix press", factory_id=F1.id, status=WorkOrderStatusEnum.COMPLETED, cost=Decimal("10.00"), created_by=U1.id, created_at=MIDT)`.
- "W2 x" / "W0 x" = builder x with `workspace_id` of that workspace and every W1 row it names replaced by that workspace's counterpart (F1, F2, FA → F9 / F0; S1 → S9 / S0; AC1 → AC9 / AC0; WT1 → WT9 / WT0).
- **voided** po / eo = `voided True`, `void_note "Void"`, `voided_at T0`, `voided_by U1.id`. **voided** wo = `status WorkOrderStatusEnum.VOIDED`. **deleted** wo = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`. **draft** po / so = `current_status_id SD.id`; draft wo = `status WorkOrderStatusEnum.DRAFT`.
- **Approver rows** (stage cards only): **poa(O, U)** = `PurchaseOrderApprover(workspace_id=O.workspace_id, purchase_order_id=O.id, user_id=U.id, assigned_at=T0)`; **soa**, **eoa**, **woa** the same with `SalesOrderApprover` / `sales_order_id`, `ExpenseOrderApprover` / `expense_order_id`, `WorkOrderApprover` / `work_order_id`. "approved" after "but" = `approved True`, `approved_at T0`.
- A Given line may build several rows separated by `;` (an order, then its lines or approvers): build them in the order written, each flushed.
- **Stage note (BUG-2480).** Outside the OQ-29 section no card reads a `…_committed` / `…_projected` field; totals and counts include every non-voided order whatever its stage, so those cards hold before and after the fix.

**Named checks.**
- **item_ids** = `[r.item_id for r in result.top_items]`; **vendor_ids** = `[r.account_id for r in result.top_vendors]`; **customer_ids** = `[r.account_id for r in result.top_customers]`; **cats** = `[r.category for r in result.top_expense_categories]`; **fids** = `[r.factory_id for r in result]` (for `get_stats`: over `result.top_factories`).
- **irow(X)** = the one row of `result.top_items` with `item_id == X.id` (the test first asserts there is exactly one). **vrow(A)**, **crow(A)** = the same over `top_vendors` / `top_customers` by `account_id`; **erow(c)** = over `top_expense_categories` by `category`; **frow(F)** = over `result` (a `_build_top_factories` list) by `factory_id`.
- **ids(q)** = `sorted(r[0] for r in q.all())` (a sorted list, so a duplicate shows).
- **recorder** = a Given step: `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `statement`; removed with `event.remove` right after the When. `statement:` lines check `stmts`. **order_part(s)** = `s.split("ORDER BY")[-1].split("LIMIT")[0]`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call. `session:` lines check `db` directly, before anything expires it.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`. Non-strict only where Expect says so. Write the call and checks as shown, also when a field does not exist yet.

**Externals.** None. **Race simulations.** None.

**Parallel runs.** `transfer_number` and `sales_order_number` are unique across all workspaces today (BUG-726 and siblings). **GN(n)** = `f"{n}-{os.getpid()}"`: the `to` and `so` builders store `GN(n)` for the card's number n (`"TO-1"` → `"TO-1-<pid>"`), so two processes never insert the same number. No card reads an order number back. PO, expense and work order numbers are unique per workspace and are stored as written.

## `_dec`

### OOV-D-01 — None becomes Decimal zero
- **Rules:** `_dec` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(None)`.

**Then**
1. returns: `result == Decimal(0)`, `isinstance(result, Decimal)`.
2. returns: `str(result) == "0"`.

### OOV-D-02 — a two-place Decimal keeps its scale
- **Rules:** `_dec` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(Decimal("12.50"))`.

**Then**
1. returns: `result == Decimal("12.50")`, `isinstance(result, Decimal)`.
2. returns: `str(result) == "12.50"`.

### OOV-D-03 — an int becomes the same whole Decimal
- **Rules:** `_dec` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(3)`.

**Then**
1. returns: `result == Decimal("3")`, `isinstance(result, Decimal)`.
2. returns: `str(result) == "3"`.

### OOV-D-04 — a float goes through its text, with no binary noise
- **Rules:** `_dec` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(0.1)`.

**Then**
1. returns: `result == Decimal("0.1")`.
2. returns: `str(result) == "0.1"`.

### OOV-D-05 — a zero value is not the None path
- **Rules:** `_dec` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(Decimal("0.00"))`.

**Then**
1. returns: `result == Decimal("0")`.
2. returns: `str(result) == "0.00"`.

### OOV-D-06 — text that is not a number raises
- **Rules:** `_dec` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec("abc")`, wrapped in `raises: InvalidOperation`.

**Then**
1. raises: `InvalidOperation` (`exc.type is InvalidOperation` or a subclass of it).

## `_po_report_date`

### OOV-RD-01 — order_date wins over created_at
- **Rules:** `_po_report_date` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. pA = po `"PO-A"`, but `order_date MID`, `created_at datetime(2026, 11, 10, 5, 40, 0)`.
2. pB = po `"PO-B"`, but `order_date date(2026, 11, 10)`, `created_at MIDT`.

**When**
- `result = ids(poq.filter(svc._in_date_range(svc._po_report_date(), START, END)))`.

**Then**
1. returns: `result == [pA.id]`.

### OOV-RD-02 — with no order_date the created_at day decides, at both edges
- **Rules:** `_po_report_date` R1, `_in_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `order_date None`, `created_at PRE_LAST`.
2. p2 = po `"PO-2"`, but `order_date None`, `created_at START_0`.
3. p3 = po `"PO-3"`, but `order_date None`, `created_at END_LAST`.
4. p4 = po `"PO-4"`, but `order_date None`, `created_at POST_0`.

**When**
- `result = ids(poq.filter(svc._in_date_range(svc._po_report_date(), START, END)))`.

**Then**
1. returns: `result == sorted([p2.id, p3.id])`.

## `_in_date_range`

### OOV-IR-01 — both ends are in, the days outside and NULL are out
- **Rules:** `_in_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `order_date PRE`.
2. p2 = po `"PO-2"`, but `order_date START`.
3. p3 = po `"PO-3"`, but `order_date END`.
4. p4 = po `"PO-4"`, but `order_date POST`.
5. p5 = po `"PO-5"`, but `order_date None`, `created_at MIDT`.

**When**
- `result = sorted(r[0] for r in db.query(PurchaseOrder.id).filter(PurchaseOrder.workspace_id == W1.id, svc._in_date_range(PurchaseOrder.order_date, START, END)).all())`.

**Then**
1. returns: `result == sorted([p2.id, p3.id])`.

### OOV-IR-02 — from after to matches nothing
- **Rules:** `_in_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. s1 = so `"SO-1"`, but `order_date START`.
2. s2 = so `"SO-2"`, but `order_date END`.

**When**
- `result = sorted(r[0] for r in db.query(SalesOrder.id).filter(SalesOrder.workspace_id == W1.id, svc._in_date_range(SalesOrder.order_date, END, START)).all())`.

**Then**
1. returns: `result == []`.

### OOV-IR-03 — a one-day range keeps that day only
- **Rules:** `_in_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. s1 = so `"SO-1"`, but `order_date PRE`.
2. s2 = so `"SO-2"`, but `order_date START`.
3. s3 = so `"SO-3"`, but `order_date date(2026, 5, 2)`.

**When**
- `result = sorted(r[0] for r in db.query(SalesOrder.id).filter(SalesOrder.workspace_id == W1.id, svc._in_date_range(SalesOrder.order_date, START, START)).all())`.

**Then**
1. returns: `result == [s2.id]`.

## `_filter_po_by_factory`

### OOV-FP-01 — storage and damaged destinations of the factory are kept
- **Rules:** `_filter_po_by_factory` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. pA = po `"PO-A"`, but `destination_id FA.id`.
2. p1 = po `"PO-1"` (storage F1).
3. p2 = po `"PO-2"`, but `destination_type "damaged"`.
4. pB = po `"PO-B"`, but `destination_id F2.id`.
5. pC = po `"PO-C"`, but `destination_type "damaged"`, `destination_id F2.id`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == sorted([p1.id, p2.id])`.

### OOV-FP-02 — a machine of the factory is kept, machines of other factories are not
- **Rules:** `_filter_po_by_factory` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. pA = po `"PO-A"`, but `destination_type "machine"`, `destination_id MA.id`.
2. p1 = po `"PO-1"`, but `destination_type "machine"`, `destination_id M1.id`.
3. pB = po `"PO-B"`, but `destination_type "machine"`, `destination_id M2.id`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == [p1.id]`.

### OOV-FP-03 — the destination type decides which table the id means
- **Rules:** `_filter_po_by_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MX = `Machine(id=XID(1), workspace_id=W1.id, factory_id=F1.id, name="Press X")`.
2. p1 = po `"PO-1"`, but `destination_type "storage"`, `destination_id XID(1)`.
3. p2 = po `"PO-2"`, but `destination_type "machine"`, `destination_id MISSING`.
4. p3 = po `"PO-3"`, but `destination_type "office"`, `destination_id F1.id`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == []`.

### OOV-FP-04 — an inactive machine still matches
- **Rules:** `_filter_po_by_factory` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `destination_type "machine"`, `destination_id MI.id`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == [p1.id]`.

### OOV-FP-05 — a deleted factory still matches its own storage
- **Rules:** `_filter_po_by_factory` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `destination_id FD.id`.
2. p2 = po `"PO-2"` (storage F1).

**When**
- `result = ids(svc._filter_po_by_factory(poq, FD.id))`.

**Then**
1. returns: `result == [p1.id]`.

### OOV-FP-06 — a machine of another workspace never matches
- **Rules:** `_filter_po_by_factory` R2a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (the foreign machines are joined by id only and both POs are kept)

**Given**
1. MZ = `Machine(workspace_id=W0.id, factory_id=F1.id, name="Stray Zero")`.
2. MX = `Machine(workspace_id=W2.id, factory_id=F1.id, name="Stray Press")`.
3. p1 = po `"PO-1"`, but `destination_type "machine"`, `destination_id MZ.id`.
4. p2 = po `"PO-2"`, but `destination_type "machine"`, `destination_id MX.id`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == []`.

### OOV-FP-07 — a PO to a component of the factory's project is kept
- **Rules:** `_filter_po_by_factory` R3 [BUG-2503]
- **Kind:** bug
- **Expect:** xfail BUG-2503
- **Fails today on:** Then 1 (the component id is looked up as a project id; no project has id XID(2))

**Given**
1. CMP = `ProjectComponent(id=XID(2), workspace_id=W1.id, project_id=PJ1.id, name="Foundation")`.
2. p1 = po `"PO-1"`, but `destination_type "project"`, `destination_id XID(2)`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == [p1.id]`.

### OOV-FP-08 — a project whose id equals the component id does not decide
- **Rules:** `_filter_po_by_factory` R3 [BUG-2503]
- **Kind:** bug
- **Expect:** xfail BUG-2503
- **Fails today on:** Then 1 (project PX, of F2, has the component's id, so the PO is kept for F2)

**Given**
1. PX = `Project(id=XID(3), workspace_id=W1.id, factory_id=F2.id, name="Side Shed", description="Main")`.
2. CMP = `ProjectComponent(id=XID(3), workspace_id=W1.id, project_id=PJ1.id, name="Roof")`.
3. p1 = po `"PO-1"`, but `destination_type "project"`, `destination_id XID(3)`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F2.id))`.

**Then**
1. returns: `result == []`.

### OOV-FP-09 — a component of another workspace matches nothing
- **Rules:** `_filter_po_by_factory` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = `Project(workspace_id=W2.id, factory_id=F9.id, name="Far Site", description="Main")`.
2. C9 = `ProjectComponent(id=XID(4), workspace_id=W2.id, project_id=P9.id, name="Far Roof")`.
3. p1 = po `"PO-1"`, but `destination_type "project"`, `destination_id XID(4)`.

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == []`.

### OOV-FP-10 — a project of another factory is dropped, whichever table the id is read in
- **Rules:** `_filter_po_by_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PX = `Project(id=XID(3), workspace_id=W1.id, factory_id=F2.id, name="Side Shed", description="Main")`.
2. CMP = `ProjectComponent(id=XID(3), workspace_id=W1.id, project_id=PX.id, name="Roof")`.
3. p1 = po `"PO-1"`, but `destination_type "project"`, `destination_id XID(3)`.
4. p2 = po `"PO-2"` (storage F1).

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == [p2.id]`.

### OOV-FP-11 — a storage id equal to a project and component id of the factory is not a project
- **Rules:** `_filter_po_by_factory` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PZ = `Project(id=XID(5), workspace_id=W1.id, factory_id=F1.id, name="North Wing", description="Main")`.
2. CZ = `ProjectComponent(id=XID(5), workspace_id=W1.id, project_id=PJ1.id, name="Wall")`.
3. p1 = po `"PO-1"`, but `destination_type "storage"`, `destination_id XID(5)`.
4. p2 = po `"PO-2"` (storage F1).

**When**
- `result = ids(svc._filter_po_by_factory(poq, F1.id))`.

**Then**
1. returns: `result == [p2.id]`.

## `_filter_transfer_by_factory`

### OOV-FT-01 — storage or damaged of the factory at either end is kept
- **Rules:** `_filter_transfer_by_factory` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"` (F2 storage → F1 storage).
2. t2 = to `"TO-2"`, but `source_location_id F1.id`, `destination_location_id F2.id`.
3. t3 = to `"TO-3"`, but `source_location_type "damaged"`, `source_location_id FA.id`, `destination_location_type "damaged"`, `destination_location_id F1.id`.
4. t4 = to `"TO-4"`, but `source_location_type "damaged"`, `source_location_id F1.id`, `destination_location_id FA.id`.
5. t5 = to `"TO-5"`, but `source_location_id FA.id`, `destination_location_id F2.id`.

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == sorted([t1.id, t2.id, t3.id, t4.id])`.

### OOV-FT-02 — a machine of the factory at either end is kept
- **Rules:** `_filter_transfer_by_factory` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`, but `destination_location_type "machine"`, `destination_location_id M1.id` (source F2 storage).
2. t2 = to `"TO-2"`, but `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "damaged"`, `destination_location_id F2.id`.
3. t3 = to `"TO-3"`, but `source_location_type "machine"`, `source_location_id MA.id`, `destination_location_type "machine"`, `destination_location_id M2.id`.

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == sorted([t1.id, t2.id])`.

### OOV-FT-03 — a transfer between two factories matches the other factory too
- **Rules:** `_filter_transfer_by_factory` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`, but `destination_location_type "machine"`, `destination_location_id M1.id` (source F2 storage).
2. t2 = to `"TO-2"`, but `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "damaged"`, `destination_location_id F2.id`.
3. t3 = to `"TO-3"`, but `source_location_type "machine"`, `source_location_id MA.id`, `destination_location_id FA.id`.

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F2.id))`.

**Then**
1. returns: `result == sorted([t1.id, t2.id])`.

### OOV-FT-04 — a project source is never considered
- **Rules:** `_filter_transfer_by_factory` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CMP = `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name="Roof")`.
2. t1 = to `"TO-1"`, but `source_location_type "project"`, `source_location_id PJ1.id`, `destination_location_id FA.id`.
3. t2 = to `"TO-2"`, but `source_location_type "project"`, `source_location_id CMP.id`, `destination_location_id FA.id`.

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == []`.

### OOV-FT-05 — inactive locations match, and a transfer inside one factory appears once
- **Rules:** `_filter_transfer_by_factory` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`, but `source_location_id FA.id`, `destination_location_type "machine"`, `destination_location_id MI.id`.
2. t2 = to `"TO-2"`, but `source_location_id F1.id`, `destination_location_type "damaged"`, `destination_location_id F1.id`.

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == sorted([t1.id, t2.id])`.

### OOV-FT-06 — a transfer to a component of the factory's project is kept
- **Rules:** `_filter_transfer_by_factory` R2 [BUG-2503]
- **Kind:** bug
- **Expect:** xfail BUG-2503
- **Fails today on:** Then 1 (the component id is looked up as a project id; no project has id XID(2))

**Given**
1. CMP = `ProjectComponent(id=XID(2), workspace_id=W1.id, project_id=PJ1.id, name="Foundation")`.
2. t1 = to `"TO-1"`, but `source_location_id FA.id`, `destination_location_type "project"`, `destination_location_id XID(2)`.

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == [t1.id]`.

### OOV-FT-07 — a machine of another workspace never matches
- **Rules:** `_filter_transfer_by_factory` R2 [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (the foreign machines are joined by id only and both transfers are kept)

**Given**
1. MZ = `Machine(workspace_id=W0.id, factory_id=F1.id, name="Stray Zero")`.
2. MX = `Machine(workspace_id=W2.id, factory_id=F1.id, name="Stray Press")`.
3. t1 = to `"TO-1"`, but `source_location_id FA.id`, `destination_location_type "machine"`, `destination_location_id MX.id`.
4. t2 = to `"TO-2"`, but `source_location_type "machine"`, `source_location_id MZ.id`, `destination_location_id FA.id`.

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == []`.

### OOV-FT-08 — a transfer to a project of another factory is dropped, whichever table the id is read in
- **Rules:** `_filter_transfer_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PX = `Project(id=XID(3), workspace_id=W1.id, factory_id=F2.id, name="Side Shed", description="Main")`.
2. CMP = `ProjectComponent(id=XID(3), workspace_id=W1.id, project_id=PX.id, name="Roof")`.
3. t1 = to `"TO-1"`, but `source_location_id FA.id`, `destination_location_type "project"`, `destination_location_id XID(3)`.
4. t2 = to `"TO-2"` (source F2 storage, destination F1 storage).

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == [t2.id]`.

### OOV-FT-09 — a storage end whose id equals a project and component id of the factory is not a project
- **Rules:** `_filter_transfer_by_factory` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PZ = `Project(id=XID(5), workspace_id=W1.id, factory_id=F1.id, name="North Wing", description="Main")`.
2. CZ = `ProjectComponent(id=XID(5), workspace_id=W1.id, project_id=PJ1.id, name="Wall")`.
3. t1 = to `"TO-1"`, but `source_location_id FA.id`, `destination_location_type "storage"`, `destination_location_id XID(5)`.
4. t2 = to `"TO-2"` (source F2 storage, destination F1 storage).

**When**
- `result = ids(svc._filter_transfer_by_factory(toq, F1.id))`.

**Then**
1. returns: `result == [t2.id]`.

## `_accumulate_factory`

### OOV-AF-01 — no factory id changes nothing
- **Rules:** `_accumulate_factory` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m = fmap()`.

**When**
- `result = svc._accumulate_factory(m, None, Decimal("5.00"), "purchase")`.

**Then**
1. returns: `result is None`.
2. returns: `len(m) == 0`.

### OOV-AF-02 — factory id 0 is credited with a new entry
- **Rules:** `_accumulate_factory` R1, R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `m = fmap()`.

**When**
- `result = svc._accumulate_factory(m, 0, Decimal("5.00"), "purchase")`.

**Then**
1. returns: `result is None`.
2. returns: `list(m) == [0]`.
3. returns: `m[0]["order_count"] == 1`, `m[0]["purchase_count"] == 1`.
4. returns: `m[0]["total_value"] == Decimal("5.00")`.
5. returns: `m[0]["transfer_count"] == 0`, `m[0]["sales_count"] == 0`, `m[0]["work_count"] == 0`.

### OOV-AF-03 — an unknown kind raises nothing, adds the order and no per-kind counter
- **Rules:** `_accumulate_factory` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `m = fmap()`.

**When**
- `svc._accumulate_factory(m, 7, Decimal("1.00"), "other")` (no exception is raised).

**Then**
1. returns: `list(m) == [7]`.
2. returns: `m[7]["order_count"] == 1`.
3. returns: `m[7]["purchase_count"] == 0`, `m[7]["transfer_count"] == 0`, `m[7]["sales_count"] == 0`, `m[7]["work_count"] == 0`.

### OOV-AF-04 — a transfer adds to transfer_count only
- **Rules:** `_accumulate_factory` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m = fmap()`.

**When**
- `svc._accumulate_factory(m, 3, Decimal("0"), "transfer")`.

**Then**
1. returns: `m[3]["order_count"] == 1`, `m[3]["transfer_count"] == 1`.
2. returns: `m[3]["purchase_count"] == 0`, `m[3]["sales_count"] == 0`, `m[3]["work_count"] == 0`.

### OOV-AF-05 — a sales order adds to sales_count only
- **Rules:** `_accumulate_factory` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m = fmap()`.

**When**
- `svc._accumulate_factory(m, 3, Decimal("2.00"), "sales")`.

**Then**
1. returns: `m[3]["order_count"] == 1`, `m[3]["sales_count"] == 1`.
2. returns: `m[3]["purchase_count"] == 0`, `m[3]["transfer_count"] == 0`, `m[3]["work_count"] == 0`.

### OOV-AF-06 — a work order adds to work_count only
- **Rules:** `_accumulate_factory` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m = fmap()`.

**When**
- `svc._accumulate_factory(m, 3, Decimal("2.00"), "work")`.

**Then**
1. returns: `m[3]["order_count"] == 1`, `m[3]["work_count"] == 1`.
2. returns: `m[3]["purchase_count"] == 0`, `m[3]["transfer_count"] == 0`, `m[3]["sales_count"] == 0`.

### OOV-AF-07 — a second purchase adds to the existing entry exactly
- **Rules:** `_accumulate_factory` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m = fmap()`.
2. `svc._accumulate_factory(m, 3, Decimal("1.25"), "purchase")` (a setup step).

**When**
- `svc._accumulate_factory(m, 3, Decimal("0.05"), "purchase")`.

**Then**
1. returns: `list(m) == [3]`.
2. returns: `m[3]["order_count"] == 2`, `m[3]["purchase_count"] == 2`.
3. returns: `m[3]["total_value"] == Decimal("1.30")`.
4. returns: `str(m[3]["total_value"]) == "1.30"`.

## `_build_top_factories`

### OOV-TF-01 — a PO to a factory's storage makes a full row
- **Rules:** `_build_top_factories` R2, R9, R10, `_factory_from_location` R1, `_accumulate_factory` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `total_amount Decimal("100.50")` (storage F1).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `len(result) == 1`, `isinstance(result[0], TopFactoryRow)`.
2. returns: `result[0].factory_id == F1.id`, `result[0].factory_name == "Factory One"`.
3. returns: `result[0].order_count == 1`, `result[0].purchase_count == 1`.
4. returns: `result[0].transfer_count == 0`, `result[0].sales_count == 0`, `result[0].work_count == 0`.
5. returns: `result[0].total_value == Decimal("100.50")`.
6. returns: `str(result[0].total_value) == "100.50"`.

### OOV-TF-02 — two POs of one factory add up exactly, damaged included
- **Rules:** `_build_top_factories` R2, `_factory_from_location` R1, `_accumulate_factory` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `total_amount Decimal("1234.56")` (storage F1).
2. p2 = po `"PO-2"`, but `destination_type "damaged"`, `total_amount Decimal("0.05")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 2`, `frow(F1).purchase_count == 2`.
3. returns: `frow(F1).total_value == Decimal("1234.61")`.
4. returns: `str(frow(F1).total_value) == "1234.61"`.

### OOV-TF-03 — a PO to a machine counts for the machine's factory; unresolved POs count nowhere
- **Rules:** `_build_top_factories` R2, `_factory_from_location` R2, R4, `_accumulate_factory` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `destination_type "machine"`, `destination_id M2.id`.
2. p2 = po `"PO-2"`, but `destination_type "machine"`, `destination_id MISSING`.
3. p3 = po `"PO-3"`, but `destination_type "office"`, `destination_id F1.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 1`, `frow(F2).purchase_count == 1`.

### OOV-TF-04 — a transfer counts for its destination's factory only and adds no value
- **Rules:** `_build_top_factories` R3, R10, `_factory_from_location` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`, but `destination_location_type "machine"`, `destination_location_id M1.id` (source F2 storage).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 1`, `frow(F1).transfer_count == 1`.
3. returns: `frow(F1).purchase_count == 0`, `frow(F1).sales_count == 0`, `frow(F1).work_count == 0`.
4. returns: `frow(F1).total_value == Decimal("0")`.

### OOV-TF-05 — with no destination factory the source decides; a project source never does
- **Rules:** `_build_top_factories` R3, `_factory_from_location` R2, R3, `_accumulate_factory` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`, but `destination_location_type "machine"`, `destination_location_id MISSING` (source F2 storage).
2. t2 = to `"TO-2"`, but `source_location_type "machine"`, `source_location_id MISSING`, `destination_location_type "machine"`, `destination_location_id MISSING`.
3. t3 = to `"TO-3"`, but `source_location_type "project"`, `source_location_id PJ1.id`, `destination_location_type "machine"`, `destination_location_id MISSING`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 1`, `frow(F2).transfer_count == 1`.

### OOV-TF-06 — a sales order counts for its own factory
- **Rules:** `_build_top_factories` R4, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. s1 = so `"SO-1"`, but `factory_id F2.id`, `total_amount Decimal("30.05")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 1`, `frow(F2).sales_count == 1`, `frow(F2).purchase_count == 0`.

### OOV-TF-07 — work orders count for their factory
- **Rules:** `_build_top_factories` R5, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. w1 = wo `"WO-1"`, but `cost Decimal("12.34")`.
2. w2 = wo `"WO-2"`, but `cost None`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 2`, `frow(F1).work_count == 2`, `frow(F1).sales_count == 0`.

### OOV-TF-08 — expense orders never count; nothing resolved gives []
- **Rules:** `_build_top_factories` R6, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. e1 = eo `"EX-1"`, but `expense_category "factory"`, `total_amount Decimal("99.00")`.
2. e2 = eo `"EX-2"`, but `account_id AC1.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `result == []`.

### OOV-TF-09 — orders of W0 and W2 count nowhere, also when they point at W1 rows
- **Rules:** `_build_top_factories` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. W0 po `"PO-Z"` (storage F0).
2. W0 to `"TO-Z"` (F0 → F0).
3. W0 so `"SO-Z"` (factory F0).
4. W0 wo `"WO-Z"` (factory F0).
5. p1 = po `"PO-1"`, but `total_amount Decimal("7.00")` (storage F1).
6. W2 po `"PO-9"` (storage F9).
7. W2 to `"TO-9"` (F9 → F9).
8. W2 so `"SO-9"` (factory F9).
9. W2 wo `"WO-9"` (factory F9).
10. W2 po `"PO-9B"`, but `destination_id F2.id`.
11. W2 so `"SO-9B"`, but `factory_id F2.id`.
12. W2 wo `"WO-9B"`, but `factory_id F2.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 1`, `frow(F1).total_value == Decimal("7.00")`.

### OOV-TF-10 — PO report days at both edges, with and without order_date
- **Rules:** `_build_top_factories` R1, `_po_report_date` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `order_date PRE` (storage F1).
2. p2 = po `"PO-2"`, but `order_date START`, `destination_id F2.id`.
3. p3 = po `"PO-3"`, but `order_date END`, `destination_id F2.id`.
4. p4 = po `"PO-4"`, but `order_date POST` (storage F1).
5. p5 = po `"PO-5"`, but `order_date None`, `created_at PRE_LAST` (storage F1).
6. p6 = po `"PO-6"`, but `order_date None`, `created_at START_0`, `destination_id F2.id`.
7. p7 = po `"PO-7"`, but `order_date None`, `created_at POST_0` (storage F1).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 3`.

### OOV-TF-11 — transfer days (created_at) at both edges
- **Rules:** `_build_top_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`, but `created_at PRE_LAST` (to F1).
2. t2 = to `"TO-2"`, but `created_at START_0`, `source_location_id FA.id`, `destination_location_id F2.id`.
3. t3 = to `"TO-3"`, but `created_at END_LAST`, `source_location_id FA.id`, `destination_location_id F2.id`.
4. t4 = to `"TO-4"`, but `created_at POST_0` (to F1).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 2`, `frow(F2).transfer_count == 2`.

### OOV-TF-12 — sales days at both edges
- **Rules:** `_build_top_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. s1 = so `"SO-1"`, but `order_date PRE`.
2. s2 = so `"SO-2"`, but `order_date START`, `factory_id F2.id`.
3. s3 = so `"SO-3"`, but `order_date END`, `factory_id F2.id`.
4. s4 = so `"SO-4"`, but `order_date POST`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 2`, `frow(F2).sales_count == 2`.

### OOV-TF-13 — work order days (created_at) at both edges
- **Rules:** `_build_top_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. w1 = wo `"WO-1"`, but `created_at PRE_LAST`.
2. w2 = wo `"WO-2"`, but `created_at START_0`, `factory_id F2.id`.
3. w3 = wo `"WO-3"`, but `created_at END_LAST`, `factory_id F2.id`.
4. w4 = wo `"WO-4"`, but `created_at POST_0`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 2`, `frow(F2).work_count == 2`.

### OOV-TF-14 — sorted by order count, then value, both descending
- **Rules:** `_build_top_factories` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. pA = po `"PO-A"`, but `destination_id FA.id`, `total_amount Decimal("500.00")`.
2. p1 = po `"PO-1"`, but `total_amount Decimal("1.00")` (storage F1).
3. p2 = po `"PO-2"`, but `total_amount Decimal("1.00")` (storage F1).
4. pB = po `"PO-B"`, but `destination_id F2.id`, `total_amount Decimal("900.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id, F2.id, FA.id]`.

### OOV-TF-15 — cut to limit after sorting
- **Rules:** `_build_top_factories` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pA1, pA2, pA3 = po `"PO-A1"`, `"PO-A2"`, `"PO-A3"`, each but `destination_id FA.id`.
2. p1 = po `"PO-1"` (storage F1).
3. pB1, pB2 = po `"PO-B1"`, `"PO-B2"`, each but `destination_id F2.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 2)`.

**Then**
1. returns: `fids == [FA.id, F2.id]`.

### OOV-TF-16 — a missing or empty factory name falls back to "Factory #id"
- **Rules:** `_build_top_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FE = `Factory(workspace_id=W1.id, name="", abbreviation="FE")`.
2. p1 = po `"PO-1"`, but `destination_id MISSING`, `total_amount Decimal("2.00")`.
3. p2 = po `"PO-2"`, but `destination_id FE.id`, `total_amount Decimal("1.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [MISSING, FE.id]`.
2. returns: `result[0].factory_name == "Factory #999999999"`.
3. returns: `result[1].factory_name == f"Factory #{FE.id}"`.

### OOV-TF-17 — storage id 0 is credited as factory 0
- **Rules:** `_accumulate_factory` R1, `_build_top_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `destination_id 0`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [0]`.
2. returns: `result[0].factory_name == "Factory #0"`, `result[0].order_count == 1`.

### OOV-TF-18 — an inactive factory is a row
- **Rules:** `_build_top_factories` R9a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `destination_id FI.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [FI.id]`.
2. returns: `result[0].factory_name == "Idle Plant"`.

### OOV-TF-19 — a deleted factory is not a row
- **Rules:** `_build_top_factories` R9a [BUG-2506]
- **Kind:** bug
- **Expect:** xfail BUG-2506
- **Fails today on:** Then 1 (FD is listed as "Old Plant")

**Given**
1. p1 = po `"PO-1"`, but `destination_id FD.id`.
2. p2 = po `"PO-2"` (storage F1).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.

### OOV-TF-20 — a voided PO counts nowhere
- **Rules:** `_build_top_factories` R2a [BUG-2500]
- **Kind:** bug
- **Expect:** xfail BUG-2500
- **Fails today on:** Then 2 (the voided PO is counted: 2 orders, 1010.00)

**Given**
1. p1 = po `"PO-1"` (storage F1, 10.00).
2. p2 = voided po `"PO-2"`, but `total_amount Decimal("1000.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 1`, `frow(F1).total_value == Decimal("10.00")`.

### OOV-TF-21 — a VOIDED work order counts nowhere
- **Rules:** `_build_top_factories` R5a [BUG-2500]
- **Kind:** bug
- **Expect:** xfail BUG-2500
- **Fails today on:** Then 2 (the voided work order is counted)

**Given**
1. w1 = wo `"WO-1"`, but `cost Decimal("5.00")`.
2. w2 = voided wo `"WO-2"`, but `cost Decimal("50.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 1`, `frow(F1).work_count == 1`.

### OOV-TF-22 — a deleted work order counts nowhere
- **Rules:** `_build_top_factories` R5a [BUG-2501]
- **Kind:** bug
- **Expect:** xfail BUG-2501
- **Fails today on:** Then 2 (the deleted work order is counted)

**Given**
1. w1 = wo `"WO-1"`, but `cost Decimal("5.00")`.
2. w2 = deleted wo `"WO-2"`, but `cost Decimal("50.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 1`, `frow(F1).work_count == 1`.

### OOV-TF-23 — a W1 sales order on another workspace's factory credits no factory
- **Rules:** `_build_top_factories` R8a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (F0 and F9 are rows, with their names)

**Given**
1. s0 = so `"SO-0"`, but `factory_id F0.id`.
2. s1 = so `"SO-1"` (factory F1).
3. s9 = so `"SO-9"`, but `factory_id F9.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `[r.factory_name for r in result] == ["Factory One"]`.

### OOV-TF-24 — a W1 work order on another workspace's factory credits no factory
- **Rules:** `_build_top_factories` R8a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (F0 and F9 are rows)

**Given**
1. w0 = wo `"WO-0"`, but `factory_id F0.id`.
2. w1 = wo `"WO-1"` (factory F1).
3. w9 = wo `"WO-9"`, but `factory_id F9.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.

### OOV-TF-25 — a W1 PO to another workspace's factory storage credits no factory
- **Rules:** `_build_top_factories` R8a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (F0 and F9 are rows)

**Given**
1. p0 = po `"PO-0"`, but `destination_id F0.id`.
2. p1 = po `"PO-1"` (storage F1).
3. p9 = po `"PO-9"`, but `destination_type "damaged"`, `destination_id F9.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.

### OOV-TF-26 — a W1 transfer to another workspace's factory credits no factory
- **Rules:** `_build_top_factories` R8a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (F0 and F9 are rows)

**Given**
1. t0 = to `"TO-0"`, but `source_location_type "machine"`, `source_location_id MISSING`, `destination_location_id F0.id`.
2. t9 = to `"TO-9"`, but `source_location_type "machine"`, `source_location_id MISSING`, `destination_location_id F9.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `result == []`.

### OOV-TF-27 — a W1 transfer from another workspace's factory credits no factory
- **Rules:** `_build_top_factories` R8a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (the source fallback credits F0 and F9)

**Given**
1. t0 = to `"TO-0"`, but `source_location_id F0.id`, `destination_location_type "machine"`, `destination_location_id MISSING`.
2. t9 = to `"TO-9"`, but `source_location_type "damaged"`, `source_location_id F9.id`, `destination_location_type "machine"`, `destination_location_id MISSING`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `result == []`.

### OOV-TF-28 — a W1 PO to another workspace's machine credits no factory
- **Rules:** `_factory_from_location` R2a [BUG-2504], `_build_top_factories` R8a
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (F0 and F9, the machines' factories, are rows)

**Given**
1. p0 = po `"PO-0"`, but `destination_type "machine"`, `destination_id M0.id`.
2. p9 = po `"PO-9"`, but `destination_type "machine"`, `destination_id M9.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `result == []`.

### OOV-TF-29 — another workspace's machine that names a W1 factory credits nothing
- **Rules:** `_factory_from_location` R2a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (F1 is credited through the W2 machine)

**Given**
1. MX = `Machine(workspace_id=W2.id, factory_id=F1.id, name="Stray Press")`.
2. p1 = po `"PO-1"`, but `destination_type "machine"`, `destination_id MX.id`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `result == []`.

### OOV-TF-30 — a PO to a project component counts for the component's project's factory
- **Rules:** `_factory_from_location` R3 [BUG-2503], `_build_top_factories` R2
- **Kind:** bug
- **Expect:** xfail BUG-2503
- **Fails today on:** Then 1 (no project has id XID(2); nothing is credited)

**Given**
1. CMP = `ProjectComponent(id=XID(2), workspace_id=W1.id, project_id=PJ1.id, name="Foundation")`.
2. p1 = po `"PO-1"`, but `destination_type "project"`, `destination_id XID(2)`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.

### OOV-TF-31 — a project with the component's id does not take the PO
- **Rules:** `_factory_from_location` R3 [BUG-2503]
- **Kind:** bug
- **Expect:** xfail BUG-2503
- **Fails today on:** Then 1 (the PO is credited to F2, factory of project PX)

**Given**
1. PX = `Project(id=XID(3), workspace_id=W1.id, factory_id=F2.id, name="Side Shed", description="Main")`.
2. CMP = `ProjectComponent(id=XID(3), workspace_id=W1.id, project_id=PJ1.id, name="Roof")`.
3. p1 = po `"PO-1"`, but `destination_type "project"`, `destination_id XID(3)`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.

### OOV-TF-32 — a transfer to a project component counts for that factory, not the source's
- **Rules:** `_factory_from_location` R3 [BUG-2503], `_build_top_factories` R3
- **Kind:** bug
- **Expect:** xfail BUG-2503
- **Fails today on:** Then 1 (the destination resolves to nothing, so the source FA is credited)

**Given**
1. CMP = `ProjectComponent(id=XID(2), workspace_id=W1.id, project_id=PJ1.id, name="Foundation")`.
2. t1 = to `"TO-1"`, but `source_location_id FA.id`, `destination_location_type "project"`, `destination_location_id XID(2)`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.

### OOV-TF-33 — tied factories are ordered by name case-insensitive before the cut
- **Rules:** `_build_top_factories` R11a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 2 (ties keep first-credited order: transfer, then sales, then work — FZ, FB)

**Given**
1. FZ = `Factory(workspace_id=W1.id, name="zeta Mill", abbreviation="FZ")`.
2. FB = `Factory(workspace_id=W1.id, name="Beta Mill", abbreviation="FB")`.
3. FC = `Factory(workspace_id=W1.id, name="alpha Mill", abbreviation="FC")`.
4. to `"TO-Z"`, but `destination_location_id FZ.id`.
5. so `"SO-B"`, but `factory_id FB.id`, `total_amount Decimal("0.00")`.
6. wo `"WO-C"`, but `factory_id FC.id`, `cost None`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 2)`.

**Then**
1. returns: `len(result) == 2`, `[r.order_count for r in result] == [1, 1]`.
2. returns: `fids == [FC.id, FB.id]`.

### OOV-TF-34 — factories tied on name case-insensitive are ordered by id
- **Rules:** `_build_top_factories` R11a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 2 (FS2 is credited first, by the transfer query, and stays first)

**Given**
1. FS1 = `Factory(workspace_id=W1.id, name="Same Mill", abbreviation="S1")`.
2. FS2 = `Factory(workspace_id=W1.id, name="SAME MILL", abbreviation="S2")` (so `FS1.id < FS2.id`).
3. to `"TO-S"`, but `destination_location_id FS2.id`.
4. wo `"WO-S"`, but `factory_id FS1.id`, `cost None`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `sorted(fids) == sorted([FS1.id, FS2.id])`.
2. returns: `fids == [FS1.id, FS2.id]`.

### OOV-TF-35 — two PO totals 0.10 + 0.20 add up exactly to 0.30
- **Rules:** `_build_top_factories` R2, `_accumulate_factory` R2; HR-15 exactness
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `total_amount Decimal("0.10")` (storage F1).
2. p2 = po `"PO-2"`, but `total_amount Decimal("0.20")` (storage F1).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).total_value == Decimal("0.30")`.
3. returns: `str(frow(F1).total_value) == "0.30"`.

### OOV-TF-36 — with the destination unresolved a source machine decides
- **Rules:** `_build_top_factories` R3, `_factory_from_location` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`, but `source_location_type "machine"`, `source_location_id M2.id`, `destination_location_type "machine"`, `destination_location_id MISSING`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).order_count == 1`, `frow(F2).transfer_count == 1`.

## `get_stats` — limit, workspace, session

### OOV-GS-01 — an empty workspace gives five empty lists
- **Rules:** `get_stats` Returns, `_build_top_factories` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only (W1 has no orders).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `isinstance(result, OrdersOverviewStatsResponse)`.
2. returns: `result.top_items == []`, `result.top_vendors == []`, `result.top_customers == []`.
3. returns: `result.top_expense_categories == []`, `result.top_factories == []`.

### OOV-GS-02 — limit 0 acts as 1 in every list
- **Rules:** `get_stats` R1, R21
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("50.00")` (storage F1).
2. pol(p1, I1, Decimal("5.00"), Decimal("50.00")).
3. p2 = po `"PO-2"`, but `account_id AC2.id`, `destination_id F2.id`, `total_amount Decimal("30.00")`.
4. pol(p2, I2, Decimal("3.00"), Decimal("30.00")).
5. s1 = so `"SO-1"`, but `total_amount Decimal("20.00")` (AC1, factory F1).
6. s2 = so `"SO-2"`, but `account_id AC2.id`, `total_amount Decimal("10.00")` (factory F1).
7. e1 = eo `"EX-1"`, but `expense_category "factory"`, `total_amount Decimal("9.00")`.
8. e2 = eo `"EX-2"`, but `total_amount Decimal("4.00")` (category "other").

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=0)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `vendor_ids == [AC1.id]`.
3. returns: `customer_ids == [AC1.id]`.
4. returns: `cats == ["factory"]`.
5. returns: `fids == [F1.id]`.

### OOV-GS-03 — limit 1 gives one row
- **Rules:** `get_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`.
2. pol(p1, I1, Decimal("5.00"), Decimal("5.00")).
3. pol(p1, I2, Decimal("3.00"), Decimal("3.00")), but `line_number 2`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=1)`.

**Then**
1. returns: `item_ids == [I1.id]`.

### OOV-GS-04 — limit 11 acts as 10
- **Rules:** `get_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Items IT1 … IT11 = `Item(workspace_id=W1.id, name=f"Part {k}", name_normalized=f"part {k}", unit="pcs")` for k = 1 … 11, in that order.
2. p1 = po `"PO-1"`.
3. For k = 1 … 11: pol(p1, ITk, Decimal(k), Decimal("1.00")), but `line_number k`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=11)`.

**Then**
1. returns: `len(result.top_items) == 10`.
2. returns: `IT1.id not in item_ids`.
3. returns: `item_ids[0] == IT11.id`.

### OOV-GS-05 — limit 10 with 11 candidates gives 10
- **Rules:** `get_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Items IT1 … IT11 = `Item(workspace_id=W1.id, name=f"Part {k}", name_normalized=f"part {k}", unit="pcs")` for k = 1 … 11, in that order.
2. p1 = po `"PO-1"`.
3. For k = 1 … 11: pol(p1, ITk, Decimal(k), Decimal("1.00")), but `line_number k`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `len(result.top_items) == 10`.
2. returns: `IT1.id not in item_ids`.

### OOV-GS-06 — the default limit is 5
- **Rules:** `get_stats` Inputs (`limit=5`), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Items IT1 … IT6 = `Item(workspace_id=W1.id, name=f"Part {k}", name_normalized=f"part {k}", unit="pcs")` for k = 1 … 6, in that order.
2. p1 = po `"PO-1"`.
3. For k = 1 … 6: pol(p1, ITk, Decimal(k), Decimal("1.00")), but `line_number k`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END)` (no `limit`).

**Then**
1. returns: `item_ids == [IT6.id, IT5.id, IT4.id, IT3.id, IT2.id]`.

### OOV-GS-07 — limit 11 acts as 10 for vendors and customers
- **Rules:** `get_stats` R1, R14, R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Accounts A1 … A11 = `Account(workspace_id=W1.id, name=f"Firm {k}")` for k = 1 … 11, in that order.
2. For k = 1 … 11: po `f"PO-{k}"`, but `account_id Ak.id`, `total_amount Decimal(k)`.
3. For k = 1 … 11: so `f"SO-{k}"`, but `account_id Ak.id`, `total_amount Decimal(k)`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=11)`.

**Then**
1. returns: `len(result.top_vendors) == 10`.
2. returns: `A1.id not in vendor_ids`.
3. returns: `len(result.top_customers) == 10`.
4. returns: `A1.id not in customer_ids`.

### OOV-GS-08 — from after to gives five empty lists
- **Rules:** `get_stats` Inputs, R2, `_in_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `order_date START`.
2. pol(p1, I1, Decimal("5.00"), Decimal("5.00")).
3. s1 = so `"SO-1"`, but `order_date END`.
4. e1 = eo `"EX-1"`, but `account_id AC2.id`, `expense_date START`.
5. w1 = wo `"WO-1"`, but `created_at END_LAST`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=END, to_date=START, limit=10)`.

**Then**
1. returns: `result.top_items == []`, `result.top_vendors == []`, `result.top_customers == []`.
2. returns: `result.top_expense_categories == []`, `result.top_factories == []`.

### OOV-GS-09 — orders of W0 and W2 count in no list
- **Rules:** `get_stats` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. pZ = W0 po `"PO-Z"`, but `account_id AC0.id`; pol(pZ, I0, Decimal("5.00"), Decimal("5.00")).
2. tZ = W0 to `"TO-Z"`; tol(tZ, I0, Decimal("5.00")).
3. sZ = W0 so `"SO-Z"`; sol(sZ, I0, Decimal("5.00"), Decimal("5.00")).
4. W0 eo `"EX-Z"`, but `account_id AC0.id`.
5. p1 = po `"PO-1"`, but `account_id AC1.id`; pol(p1, I1, Decimal("1.00"), Decimal("1.00")).
6. s1 = so `"SO-1"` (AC1, factory F1).
7. e1 = eo `"EX-1"`, but `account_id AC1.id`.
8. p9 = W2 po `"PO-9"`, but `account_id AC9.id`; pol(p9, I9, Decimal("5.00"), Decimal("5.00")).
9. t9 = W2 to `"TO-9"`; tol(t9, I9, Decimal("5.00")).
10. s9 = W2 so `"SO-9"`; sol(s9, I9, Decimal("5.00"), Decimal("5.00")).
11. W2 eo `"EX-9"`, but `account_id AC9.id`, `expense_category "department"`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `vendor_ids == [AC1.id]`.
3. returns: `customer_ids == [AC1.id]`.
4. returns: `cats == ["other"]`.
5. returns: `fids == [F1.id]`.

### OOV-GS-10 — W2 orders that point at W1 rows count in no list
- **Rules:** `get_stats` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. p9 = W2 po `"PO-9"`, but `account_id AC1.id`, `destination_id F1.id`; pol(p9, I1, Decimal("5.00"), Decimal("5.00")).
2. t9 = W2 to `"TO-9"`, but `destination_location_id F1.id`; tol(t9, I2, Decimal("5.00")).
3. s9 = W2 so `"SO-9"`, but `account_id AC1.id`, `factory_id F1.id`; sol(s9, I3, Decimal("5.00"), Decimal("5.00")).
4. W2 eo `"EX-9"`, but `account_id AC1.id`.
5. W2 wo `"WO-9"`, but `factory_id F1.id`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `result.top_items == []`, `result.top_vendors == []`, `result.top_customers == []`.
2. returns: `result.top_expense_categories == []`, `result.top_factories == []`.

### OOV-GS-11 — the read neither commits nor rolls back
- **Rules:** `get_stats` R2 (TC6)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`; pol(p1, I1, Decimal("1.00"), Decimal("1.00")).
2. spies around the When.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.

### OOV-GS-12 — pending changes stay pending
- **Rules:** `get_stats` R2 (TC6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `NEW = Item(workspace_id=W1.id, name="Pending", name_normalized="pending", unit="pcs")`; `db.add(NEW)`, not flushed.
2. `I1.name = "Bolt Edited"`, not flushed.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `result.top_items == []`.
2. session: `NEW in db.new`, `len(db.new) == 1`.
3. session: `I1 in db.dirty`, `len(db.dirty) == 1`.
4. session: `I1.name == "Bolt Edited"`.

### OOV-GS-13 — a database error reaches the caller unchanged
- **Rules:** `get_stats` R2 (TC6)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `E = RuntimeError("boom")`.
2. spies, and inside them `patch.object(db, "query", side_effect=E)`, around the When.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`, wrapped in `raises: RuntimeError`.

**Then**
1. raises: `exc.value is E`.
2. mock called: `rb.call_count == 0`, `cm.call_count == 0`.

### OOV-GS-14 — the read writes nothing
- **Rules:** `get_stats` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`; pol(p1, I1, Decimal("1.00"), Decimal("1.00")).
2. recorder around the When.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. statement: `[s for s in stmts if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))] == []`.
3. statement: `len(stmts) >= 1`.

### OOV-GS-15 — lines are scoped by their order's workspace, not their own
- **Rules:** `get_stats` R2 (Facts: line `workspace_id` is never read)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`; then `PurchaseOrderItem(workspace_id=W2.id, purchase_order_id=p1.id, line_number=1, item_id=I1.id, quantity_ordered=Decimal("4.00"), line_subtotal=Decimal("4.00"))`.
2. t1 = to `"TO-1"`; then `TransferOrderItem(workspace_id=W0.id, transfer_order_id=t1.id, line_number=1, item_id=I1.id, quantity=Decimal("2.00"))`.
3. p9 = W2 po `"PO-9"`; then `PurchaseOrderItem(workspace_id=W1.id, purchase_order_id=p9.id, line_number=1, item_id=I2.id, quantity_ordered=Decimal("9.00"), line_subtotal=Decimal("9.00"))`.
4. t0 = W0 to `"TO-0"`; then `TransferOrderItem(workspace_id=W1.id, transfer_order_id=t0.id, line_number=1, item_id=I3.id, quantity=Decimal("7.00"))`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).purchase_qty == Decimal("4.00")`, `irow(I1).transfer_qty == Decimal("2.00")`, `irow(I1).line_count == 2`.

## `get_stats` — top items

### OOV-TI-01 — one PO line fills every field of the item row
- **Rules:** `get_stats` R3, R4, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`.
2. pol(p1, I1, Decimal("50.00"), Decimal("1234.56")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).item_name == "Bolt"`, `irow(I1).item_unit == "pcs"`, `irow(I1).line_count == 1`.
3. returns: `irow(I1).total_quantity == Decimal("50.00")`, `irow(I1).purchase_qty == Decimal("50.00")`.
4. returns: `str(irow(I1).purchase_qty) == "50.00"`.
5. returns: `irow(I1).transfer_qty == Decimal("0")`, `irow(I1).sales_qty == Decimal("0")`.
6. returns: `str(irow(I1).transfer_qty) == "0"`.
7. returns: `irow(I1).total_spend == Decimal("1234.56")`.
8. returns: `str(irow(I1).total_spend) == "1234.56"`.

### OOV-TI-02 — lines of one item on two POs add up exactly
- **Rules:** `get_stats` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`.
2. pol(p1, I1, Decimal("10.00"), Decimal("0.05")).
3. p2 = po `"PO-2"`, but `destination_id F2.id`.
4. pol(p2, I1, Decimal("5.50"), Decimal("1234.56")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).total_quantity == Decimal("15.50")`, `irow(I1).purchase_qty == Decimal("15.50")`.
3. returns: `irow(I1).total_spend == Decimal("1234.61")`.
4. returns: `str(irow(I1).total_spend) == "1234.61"`.
5. returns: `irow(I1).line_count == 2`.

### OOV-TI-03 — a line with no subtotal adds no spend
- **Rules:** `get_stats` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`.
2. pol(p1, I1, Decimal("3.00"), None).
3. pol(p1, I1, Decimal("1.00"), Decimal("2.00")), but `line_number 2`.
4. p2 = po `"PO-2"`.
5. pol(p2, I2, Decimal("1.00"), None).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id, I2.id]`.
2. returns: `irow(I1).total_spend == Decimal("2.00")`, `irow(I1).line_count == 2`.
3. returns: `irow(I2).total_spend == Decimal("0")`, `irow(I2).line_count == 1`.

### OOV-TI-04 — a transfer line adds quantity but no spend
- **Rules:** `get_stats` R3, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. t1 = to `"TO-1"`.
2. tol(t1, I1, Decimal("7.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).transfer_qty == Decimal("7.00")`, `irow(I1).total_quantity == Decimal("7.00")`.
3. returns: `irow(I1).purchase_qty == Decimal("0")`, `irow(I1).sales_qty == Decimal("0")`.
4. returns: `irow(I1).total_spend == Decimal("0")`, `irow(I1).line_count == 1`.

### OOV-TI-05 — a sales line adds quantity; a free-text line is not counted
- **Rules:** `get_stats` R3, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. s1 = so `"SO-1"`.
2. sol(s1, I1, Decimal("3.00"), Decimal("300.00")).
3. free-text sol on s1: `SalesOrderItem(workspace_id=W1.id, sales_order_id=s1.id, item_id=None, description="Line", quantity_ordered=Decimal("9.00"), unit_price=Decimal("1.00"), line_total=Decimal("900.00"))`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).sales_qty == Decimal("3.00")`, `irow(I1).total_quantity == Decimal("3.00")`.
3. returns: `irow(I1).purchase_qty == Decimal("0")`, `irow(I1).transfer_qty == Decimal("0")`.
4. returns: `irow(I1).line_count == 1`.

### OOV-TI-06 — an item with an empty name is "Item #id", with its unit
- **Rules:** `get_stats` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IE = `Item(workspace_id=W1.id, name="", name_normalized="", unit="kg")`.
2. p1 = po `"PO-1"`.
3. pol(p1, IE, Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [IE.id]`.
2. returns: `irow(IE).item_name == f"Item #{IE.id}"`, `irow(IE).item_unit == "kg"`.

### OOV-TI-07 — items sorted by quantity, then spend, both descending
- **Rules:** `get_stats` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`.
2. pol(p1, I1, Decimal("10.00"), Decimal("5.00")).
3. pol(p1, I2, Decimal("20.00"), Decimal("1.00")), but `line_number 2`.
4. pol(p1, I3, Decimal("10.00"), Decimal("9.00")), but `line_number 3`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I2.id, I3.id, I1.id]`.

### OOV-TI-08 — items cut to limit after sorting
- **Rules:** `get_stats` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`.
2. pol(p1, I1, Decimal("1.00"), Decimal("1.00")).
3. pol(p1, I2, Decimal("3.00"), Decimal("1.00")), but `line_number 2`.
4. pol(p1, I3, Decimal("2.00"), Decimal("1.00")), but `line_number 3`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `item_ids == [I2.id, I3.id]`.

### OOV-TI-09 — PO lines: report days at both edges, with and without order_date
- **Rules:** `get_stats` R2, R4, `_po_report_date` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pa = po `"PO-A"`, but `order_date PRE`; pol(pa, I1, Decimal("1.00"), Decimal("1.00")).
2. pb = po `"PO-B"`, but `order_date START`; pol(pb, I1, Decimal("10.00"), Decimal("1.00")).
3. pc = po `"PO-C"`, but `order_date END`; pol(pc, I1, Decimal("100.00"), Decimal("1.00")).
4. pd = po `"PO-D"`, but `order_date POST`; pol(pd, I1, Decimal("1000.00"), Decimal("1.00")).
5. pe = po `"PO-E"`, but `order_date None`, `created_at END_LAST`; pol(pe, I1, Decimal("10000.00"), Decimal("1.00")).
6. pf = po `"PO-F"`, but `order_date None`, `created_at PRE_LAST`; pol(pf, I1, Decimal("100000.00"), Decimal("1.00")).
7. pg = po `"PO-G"`, but `order_date None`, `created_at POST_0`; pol(pg, I1, Decimal("1000000.00"), Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `irow(I1).purchase_qty == Decimal("10110.00")`, `irow(I1).line_count == 3`.

### OOV-TI-10 — transfer lines: created_at days at both edges
- **Rules:** `get_stats` R2, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. ta = to `"TO-A"`, but `created_at PRE_LAST`; tol(ta, I1, Decimal("1.00")).
2. tb = to `"TO-B"`, but `created_at START_0`; tol(tb, I1, Decimal("10.00")).
3. tc = to `"TO-C"`, but `created_at END_LAST`; tol(tc, I1, Decimal("100.00")).
4. td = to `"TO-D"`, but `created_at POST_0`; tol(td, I1, Decimal("1000.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `irow(I1).transfer_qty == Decimal("110.00")`, `irow(I1).line_count == 2`.

### OOV-TI-11 — sales lines: order days at both edges
- **Rules:** `get_stats` R2, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. sa = so `"SO-A"`, but `order_date PRE`; sol(sa, I1, Decimal("1.00"), Decimal("1.00")).
2. sb = so `"SO-B"`, but `order_date START`; sol(sb, I1, Decimal("10.00"), Decimal("1.00")).
3. sc = so `"SO-C"`, but `order_date END`; sol(sc, I1, Decimal("100.00"), Decimal("1.00")).
4. sd = so `"SO-D"`, but `order_date POST`; sol(sd, I1, Decimal("1000.00"), Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `irow(I1).sales_qty == Decimal("110.00")`, `irow(I1).line_count == 2`.

### OOV-TI-12 — lines of a voided PO count nowhere
- **Rules:** `get_stats` R4a [BUG-2500]
- **Kind:** bug
- **Expect:** xfail BUG-2500
- **Fails today on:** Then 2 (the voided PO's 50 units and 1000.00 are counted)

**Given**
1. p1 = po `"PO-1"`; pol(p1, I1, Decimal("5.00"), Decimal("10.00")).
2. p2 = voided po `"PO-2"`; pol(p2, I1, Decimal("50.00"), Decimal("1000.00")).
3. p3 = voided po `"PO-3"`; pol(p3, I2, Decimal("9.00"), Decimal("9.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `I1.id in item_ids`.
2. returns: `irow(I1).purchase_qty == Decimal("5.00")`, `irow(I1).total_spend == Decimal("10.00")`, `irow(I1).line_count == 1`.
3. returns: `item_ids == [I1.id]`.

### OOV-TI-13 — a PO line of another workspace's item is left out
- **Rules:** `get_stats` R6a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (I0 and I9 are rows with their names)

**Given**
1. p1 = po `"PO-1"`.
2. pol(p1, I0, Decimal("5.00"), Decimal("5.00")).
3. pol(p1, I1, Decimal("1.00"), Decimal("1.00")), but `line_number 2`.
4. pol(p1, I9, Decimal("7.00"), Decimal("7.00")), but `line_number 3`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.

### OOV-TI-14 — a transfer line of another workspace's item is left out
- **Rules:** `get_stats` R6a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (I0 and I9 are rows)

**Given**
1. t1 = to `"TO-1"`.
2. tol(t1, I0, Decimal("5.00")).
3. tol(t1, I1, Decimal("1.00")), but `line_number 2`.
4. tol(t1, I9, Decimal("7.00")), but `line_number 3`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.

### OOV-TI-15 — a sales line of another workspace's item is left out
- **Rules:** `get_stats` R6a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (I0 and I9 are rows)

**Given**
1. s1 = so `"SO-1"`.
2. sol(s1, I0, Decimal("5.00"), Decimal("5.00")).
3. sol(s1, I1, Decimal("1.00"), Decimal("1.00")).
4. sol(s1, I9, Decimal("7.00"), Decimal("7.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.

### OOV-TI-16 — tied items are ordered by name case-insensitive before the cut
- **Rules:** `get_stats` R9a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 2 (ties keep first-seen order: the two transfer lines come before the sales line, so IA is cut)

**Given**
1. IZ = `Item(workspace_id=W1.id, name="zeta Rod", name_normalized="zeta rod", unit="pcs")`.
2. IB = `Item(workspace_id=W1.id, name="Beta Rod", name_normalized="beta rod", unit="pcs")`.
3. IA = `Item(workspace_id=W1.id, name="alpha Rod", name_normalized="alpha rod", unit="pcs")`.
4. t1 = to `"TO-1"`; tol(t1, IZ, Decimal("5.00")); tol(t1, IB, Decimal("5.00")), but `line_number 2`.
5. s1 = so `"SO-1"`; sol(s1, IA, Decimal("5.00"), Decimal("0.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `len(result.top_items) == 2`.
2. returns: `item_ids == [IA.id, IB.id]`.

### OOV-TI-17 — items tied on name case-insensitive are ordered by id
- **Rules:** `get_stats` R9a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 2 (IS2's transfer line is seen first and stays first)

**Given**
1. IS1 = `Item(workspace_id=W1.id, name="Same Rod", name_normalized="same rod", unit="pcs")`.
2. IS2 = `Item(workspace_id=W1.id, name="SAME ROD", name_normalized="same rod", unit="pcs")` (so `IS1.id < IS2.id`).
3. t1 = to `"TO-1"`; tol(t1, IS2, Decimal("5.00")).
4. s1 = so `"SO-1"`; sol(s1, IS1, Decimal("5.00"), Decimal("0.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `sorted(item_ids) == sorted([IS1.id, IS2.id])`.
2. returns: `item_ids == [IS1.id, IS2.id]`.

### OOV-TI-18 — an item seen only on transfer lines is named with its unit; an empty name falls back
- **Rules:** `get_stats` R6, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. IE = `Item(workspace_id=W1.id, name="", name_normalized="", unit="box")`.
2. t1 = to `"TO-1"`; tol(t1, I2, Decimal("3.00")).
3. t2 = to `"TO-2"`; tol(t2, IE, Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `sorted(item_ids) == sorted([I2.id, IE.id])`.
2. returns: `irow(I2).item_name == "Nut"`, `irow(I2).item_unit == "pcs"`.
3. returns: `irow(IE).item_name == f"Item #{IE.id}"`, `irow(IE).item_unit == "box"`.
4. returns: `irow(I2).transfer_qty == Decimal("3.00")`.

### OOV-TI-19 — an item seen only on sales lines is named with its unit; an empty name falls back
- **Rules:** `get_stats` R6, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. IS = `Item(workspace_id=W1.id, name="", name_normalized="", unit="kg")`.
2. s1 = so `"SO-1"`; sol(s1, I3, Decimal("2.00"), Decimal("8.00")).
3. s2 = so `"SO-2"`; sol(s2, IS, Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `sorted(item_ids) == sorted([I3.id, IS.id])`.
2. returns: `irow(I3).item_name == "Washer"`, `irow(I3).item_unit == "pcs"`.
3. returns: `irow(IS).item_name == f"Item #{IS.id}"`, `irow(IS).item_unit == "kg"`.
4. returns: `irow(I3).sales_qty == Decimal("2.00")`.

### OOV-TI-20 — an empty unit is shown as no unit, on every line kind
- **Rules:** `get_stats` R8c
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IP = `Item(workspace_id=W1.id, name="Pipe", name_normalized="pipe", unit="")`.
2. IT = `Item(workspace_id=W1.id, name="Tape", name_normalized="tape", unit="")`.
3. IQ = `Item(workspace_id=W1.id, name="Quill", name_normalized="quill", unit="")`.
4. p1 = po `"PO-1"`; pol(p1, IP, Decimal("1.00"), Decimal("1.00")).
5. t1 = to `"TO-1"`; tol(t1, IT, Decimal("1.00")).
6. s1 = so `"SO-1"`; sol(s1, IQ, Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `sorted(item_ids) == sorted([IP.id, IT.id, IQ.id])`.
2. returns: `irow(IP).item_unit is None`, `irow(IP).item_name == "Pipe"`.
3. returns: `irow(IT).item_unit is None`, `irow(IT).item_name == "Tape"`.
4. returns: `irow(IQ).item_unit is None`, `irow(IQ).item_name == "Quill"`.

### OOV-TI-21 — PO line subtotals 0.10 + 0.20 add up exactly to 0.30
- **Rules:** `get_stats` R4; HR-15 exactness
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`; pol(p1, I1, Decimal("1.00"), Decimal("0.10")).
2. p2 = po `"PO-2"`; pol(p2, I1, Decimal("1.00"), Decimal("0.20")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).total_spend == Decimal("0.30")`.
3. returns: `str(irow(I1).total_spend) == "0.30"`.

## `get_stats` — top vendors

### OOV-TV-01 — a PO with an account makes a vendor row
- **Rules:** `get_stats` R10, R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("1234.56")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. returns: `vrow(AC1).account_name == "Acme"`, `vrow(AC1).order_count == 1`.
3. returns: `vrow(AC1).total_spend == Decimal("1234.56")`.
4. returns: `str(vrow(AC1).total_spend) == "1234.56"`.

### OOV-TV-02 — POs and expense orders of one account make one row
- **Rules:** `get_stats` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("100.00")`.
2. e1 = eo `"EX-1"`, but `account_id AC1.id`, `total_amount Decimal("0.05")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. returns: `vrow(AC1).total_spend == Decimal("100.05")`, `vrow(AC1).order_count == 2`.
3. returns: `str(vrow(AC1).total_spend) == "100.05"`.

### OOV-TV-03 — orders without an account are left out
- **Rules:** `get_stats` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `total_amount Decimal("500.00")` (no account).
2. e1 = eo `"EX-1"`, but `total_amount Decimal("600.00")` (no account).
3. p2 = po `"PO-2"`, but `account_id AC2.id`, `total_amount Decimal("1.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC2.id]`.
2. returns: `vrow(AC2).total_spend == Decimal("1.00")`, `vrow(AC2).order_count == 1`.

### OOV-TV-04 — empty name falls back; a deleted account keeps its row and name
- **Rules:** `get_stats` R13
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AE = `Account(workspace_id=W1.id, name="")`.
2. AX = `Account(workspace_id=W1.id, name="Gone Co", is_deleted=True, is_active=False, deleted_at=T0, deleted_by=U1.id)`.
3. p1 = po `"PO-1"`, but `account_id AE.id`, `total_amount Decimal("2.00")`.
4. e1 = eo `"EX-1"`, but `account_id AX.id`, `total_amount Decimal("1.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AE.id, AX.id]`.
2. returns: `vrow(AE).account_name == f"Account #{AE.id}"`.
3. returns: `vrow(AX).account_name == "Gone Co"`.

### OOV-TV-05 — vendors sorted by spend descending and cut to limit
- **Rules:** `get_stats` R14
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("10.00")`.
2. p2 = po `"PO-2"`, but `account_id AC2.id`, `total_amount Decimal("30.00")`.
3. e3 = eo `"EX-3"`, but `account_id AC3.id`, `total_amount Decimal("20.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `vendor_ids == [AC2.id, AC3.id]`.

### OOV-TV-06 — PO vendors: report days at both edges, with and without order_date
- **Rules:** `get_stats` R2, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. po `"PO-A"`, but `account_id AC1.id`, `order_date PRE`, `total_amount Decimal("1.00")`.
2. po `"PO-B"`, but `account_id AC1.id`, `order_date START`, `total_amount Decimal("10.00")`.
3. po `"PO-C"`, but `account_id AC1.id`, `order_date END`, `total_amount Decimal("100.00")`.
4. po `"PO-D"`, but `account_id AC1.id`, `order_date POST`, `total_amount Decimal("1000.00")`.
5. po `"PO-E"`, but `account_id AC1.id`, `order_date None`, `created_at START_0`, `total_amount Decimal("10000.00")`.
6. po `"PO-F"`, but `account_id AC1.id`, `order_date None`, `created_at PRE_LAST`, `total_amount Decimal("100000.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vrow(AC1).total_spend == Decimal("10110.00")`, `vrow(AC1).order_count == 3`.

### OOV-TV-07 — expense vendors: expense days at both edges
- **Rules:** `get_stats` R2, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. eo `"EX-A"`, but `account_id AC1.id`, `expense_date PRE`, `total_amount Decimal("1.00")`.
2. eo `"EX-B"`, but `account_id AC1.id`, `expense_date START`, `total_amount Decimal("10.00")`.
3. eo `"EX-C"`, but `account_id AC1.id`, `expense_date END`, `total_amount Decimal("100.00")`.
4. eo `"EX-D"`, but `account_id AC1.id`, `expense_date POST`, `total_amount Decimal("1000.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vrow(AC1).total_spend == Decimal("110.00")`, `vrow(AC1).order_count == 2`.

### OOV-TV-08 — a voided PO counts in no vendor
- **Rules:** `get_stats` R11a [BUG-2500]
- **Kind:** bug
- **Expect:** xfail BUG-2500
- **Fails today on:** Then 2 (the voided 1000.00 is in AC1's spend)

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("10.00")`.
2. p2 = voided po `"PO-2"`, but `account_id AC1.id`, `total_amount Decimal("1000.00")`.
3. p3 = voided po `"PO-3"`, but `account_id AC2.id`, `total_amount Decimal("5.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `AC1.id in vendor_ids`.
2. returns: `vrow(AC1).total_spend == Decimal("10.00")`, `vrow(AC1).order_count == 1`.
3. returns: `vendor_ids == [AC1.id]`.

### OOV-TV-09 — a voided expense order counts in no vendor
- **Rules:** `get_stats` R11a [BUG-2500]
- **Kind:** bug
- **Expect:** xfail BUG-2500
- **Fails today on:** Then 2 (the voided 300.00 is in AC1's spend)

**Given**
1. e1 = eo `"EX-1"`, but `account_id AC1.id`, `total_amount Decimal("10.00")`.
2. e2 = voided eo `"EX-2"`, but `account_id AC1.id`, `total_amount Decimal("300.00")`.
3. e3 = voided eo `"EX-3"`, but `account_id AC2.id`, `total_amount Decimal("5.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `AC1.id in vendor_ids`.
2. returns: `vrow(AC1).total_spend == Decimal("10.00")`, `vrow(AC1).order_count == 1`.
3. returns: `vendor_ids == [AC1.id]`.

### OOV-TV-10 — a W1 PO with another workspace's account is left out
- **Rules:** `get_stats` R13a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (AC0 "Zero Co" and AC9 "Far Co" are rows)

**Given**
1. po `"PO-0"`, but `account_id AC0.id`, `total_amount Decimal("50.00")`.
2. po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("1.00")`.
3. po `"PO-9"`, but `account_id AC9.id`, `total_amount Decimal("90.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.

### OOV-TV-11 — a W1 expense order with another workspace's account is left out
- **Rules:** `get_stats` R13a [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (AC0 and AC9 are rows)

**Given**
1. eo `"EX-0"`, but `account_id AC0.id`, `total_amount Decimal("50.00")`.
2. eo `"EX-1"`, but `account_id AC1.id`, `total_amount Decimal("1.00")`.
3. eo `"EX-9"`, but `account_id AC9.id`, `total_amount Decimal("90.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.

### OOV-TV-12 — tied vendors are ordered by name case-insensitive before the cut
- **Rules:** `get_stats` R14a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 2 (PO vendors come before expense-only vendors, so AA is cut)

**Given**
1. AZ = `Account(workspace_id=W1.id, name="zeta Supply")`.
2. AB = `Account(workspace_id=W1.id, name="Beta Supply")`.
3. AA = `Account(workspace_id=W1.id, name="alpha Supply")`.
4. po `"PO-Z"`, but `account_id AZ.id`; po `"PO-B"`, but `account_id AB.id` (each 10.00).
5. eo `"EX-A"`, but `account_id AA.id` (10.00).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `len(result.top_vendors) == 2`.
2. returns: `vendor_ids == [AA.id, AB.id]`.

### OOV-TV-13 — vendors tied on name case-insensitive are ordered by id
- **Rules:** `get_stats` R14a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 2 (AS2, a PO vendor, comes before the expense-only AS1)

**Given**
1. AS1 = `Account(workspace_id=W1.id, name="Same Supply")`.
2. AS2 = `Account(workspace_id=W1.id, name="SAME SUPPLY")` (so `AS1.id < AS2.id`).
3. po `"PO-S"`, but `account_id AS2.id` (10.00).
4. eo `"EX-S"`, but `account_id AS1.id` (10.00).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `sorted(vendor_ids) == sorted([AS1.id, AS2.id])`.
2. returns: `vendor_ids == [AS1.id, AS2.id]`.

### OOV-TV-14 — sales orders never count in top vendors
- **Rules:** `get_stats` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("10.00")`.
2. so `"SO-1"`, but `total_amount Decimal("50.00")` (AC1).
3. so `"SO-2"`, but `account_id AC3.id`, `total_amount Decimal("7.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. returns: `vrow(AC1).total_spend == Decimal("10.00")`, `vrow(AC1).order_count == 1`.

### OOV-TV-15 — a deleted account keeps its PO vendor row and name
- **Rules:** `get_stats` R13
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AX = `Account(workspace_id=W1.id, name="Gone Co", is_deleted=True, is_active=False, deleted_at=T0, deleted_by=U1.id)`.
2. p1 = po `"PO-1"`, but `account_id AX.id`, `total_amount Decimal("3.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AX.id]`.
2. returns: `vrow(AX).account_name == "Gone Co"`, `vrow(AX).total_spend == Decimal("3.00")`.

### OOV-TV-16 — an expense-only vendor with an empty name falls back to Account #id
- **Rules:** `get_stats` R10, R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AE = `Account(workspace_id=W1.id, name="")`.
2. e1 = eo `"EX-1"`, but `account_id AE.id`, `total_amount Decimal("4.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AE.id]`.
2. returns: `vrow(AE).account_name == f"Account #{AE.id}"`, `vrow(AE).order_count == 1`.

### OOV-TV-17 — PO and expense totals 0.10 + 0.20 add up exactly to 0.30
- **Rules:** `get_stats` R10; HR-15 exactness
- **Kind:** boundary
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("0.10")`.
2. e1 = eo `"EX-1"`, but `account_id AC1.id`, `total_amount Decimal("0.20")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. returns: `vrow(AC1).total_spend == Decimal("0.30")`.
3. returns: `str(vrow(AC1).total_spend) == "0.30"`.

## `get_stats` — top customers

### OOV-TC-01 — sales orders grouped by account with exact sums and counts
- **Rules:** `get_stats` R16, R17
- **Kind:** happy
- **Expect:** pass

**Given**
1. so `"SO-1"`, but `total_amount Decimal("1234.56")` (AC1).
2. so `"SO-2"`, but `total_amount Decimal("0.05")` (AC1).
3. so `"SO-3"`, but `account_id AC2.id`, `total_amount Decimal("7.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `customer_ids == [AC1.id, AC2.id]`.
2. returns: `crow(AC1).account_name == "Acme"`, `crow(AC1).order_count == 2`.
3. returns: `crow(AC1).total_spend == Decimal("1234.61")`.
4. returns: `str(crow(AC1).total_spend) == "1234.61"`.
5. returns: `crow(AC2).account_name == "Beta"`, `crow(AC2).order_count == 1`, `crow(AC2).total_spend == Decimal("7.00")`.

### OOV-TC-02 — empty customer name falls back; a deleted account keeps its row
- **Rules:** `get_stats` R16 (name as R13)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AE = `Account(workspace_id=W1.id, name="")`.
2. AX = `Account(workspace_id=W1.id, name="Gone Co", is_deleted=True, is_active=False, deleted_at=T0, deleted_by=U1.id)`.
3. so `"SO-1"`, but `account_id AE.id`, `total_amount Decimal("2.00")`.
4. so `"SO-2"`, but `account_id AX.id`, `total_amount Decimal("1.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `customer_ids == [AE.id, AX.id]`.
2. returns: `crow(AE).account_name == f"Account #{AE.id}"`.
3. returns: `crow(AX).account_name == "Gone Co"`.

### OOV-TC-03 — customers sorted by total descending and cut to limit
- **Rules:** `get_stats` R17
- **Kind:** happy
- **Expect:** pass

**Given**
1. so `"SO-1"`, but `total_amount Decimal("10.00")` (AC1).
2. so `"SO-2"`, but `account_id AC2.id`, `total_amount Decimal("30.00")`.
3. so `"SO-3"`, but `account_id AC3.id`, `total_amount Decimal("20.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `customer_ids == [AC2.id, AC3.id]`.

### OOV-TC-04 — sales days at both edges
- **Rules:** `get_stats` R2, R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. so `"SO-A"`, but `order_date PRE`, `total_amount Decimal("1.00")`.
2. so `"SO-B"`, but `order_date START`, `total_amount Decimal("10.00")`.
3. so `"SO-C"`, but `order_date END`, `total_amount Decimal("100.00")`.
4. so `"SO-D"`, but `order_date POST`, `total_amount Decimal("1000.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `crow(AC1).total_spend == Decimal("110.00")`, `crow(AC1).order_count == 2`.

### OOV-TC-05 — a W1 sales order with another workspace's account is left out
- **Rules:** `get_stats` R16 [BUG-2504]
- **Kind:** bug
- **Expect:** xfail BUG-2504
- **Fails today on:** Then 1 (AC0 and AC9 are rows)

**Given**
1. so `"SO-0"`, but `account_id AC0.id`, `total_amount Decimal("50.00")`.
2. so `"SO-1"`, but `total_amount Decimal("1.00")` (AC1).
3. so `"SO-9"`, but `account_id AC9.id`, `total_amount Decimal("90.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `customer_ids == [AC1.id]`.

### OOV-TC-06 — tied customers are ordered by name case-insensitive, then id
- **Rules:** `get_stats` R17a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (ties keep the query's row order; may hold by chance)

**Given**
1. AZ = `Account(workspace_id=W1.id, name="zeta Buyer")`.
2. AB = `Account(workspace_id=W1.id, name="Beta Buyer")`.
3. AA = `Account(workspace_id=W1.id, name="alpha Buyer")`.
4. so `"SO-Z"`, but `account_id AZ.id`; so `"SO-B"`, but `account_id AB.id`; so `"SO-A"`, but `account_id AA.id` (each 10.00, built in that order).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `customer_ids == [AA.id, AB.id]`.

### OOV-TC-07 — the customers' SQL cut orders by name and id after the total
- **Rules:** `get_stats` R17, R17a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 3 (today the ORDER BY has the summed total only)

**Given**
1. so `"SO-1"`, but `total_amount Decimal("10.00")` (AC1).
2. recorder around the When.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `customer_ids == [AC1.id]`.
2. statement: `cs = [s for s in stmts if "sales_orders" in s and "GROUP BY" in s and "LIMIT" in s]`; `len(cs) == 1`.
3. statement: `"name" in order_part(cs[0])`.
4. statement: `"accounts.id" in order_part(cs[0]) or "account_id" in order_part(cs[0])`.

### OOV-TC-08 — sales totals 0.10 + 0.20 add up exactly to 0.30
- **Rules:** `get_stats` R16; HR-15 exactness
- **Kind:** boundary
- **Expect:** pass

**Given**
1. so `"SO-1"`, but `total_amount Decimal("0.10")` (AC1).
2. so `"SO-2"`, but `total_amount Decimal("0.20")` (AC1).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `customer_ids == [AC1.id]`.
2. returns: `crow(AC1).total_spend == Decimal("0.30")`.
3. returns: `str(crow(AC1).total_spend) == "0.30"`.

## `get_stats` — top expense categories

### OOV-TE-01 — expense orders grouped by category, with or without an account
- **Rules:** `get_stats` R19
- **Kind:** happy
- **Expect:** pass

**Given**
1. eo `"EX-1"`, but `expense_category "factory"`, `total_amount Decimal("1234.56")`.
2. eo `"EX-2"`, but `expense_category "factory"`, `account_id AC1.id`, `total_amount Decimal("0.05")`.
3. eo `"EX-3"`, but `total_amount Decimal("7.00")` (category "other").

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `cats == ["factory", "other"]`.
2. returns: `result.top_expense_categories[0].total_spend == Decimal("1234.61")`, `result.top_expense_categories[0].order_count == 2`.
3. returns: `str(result.top_expense_categories[0].total_spend) == "1234.61"`.
4. returns: `result.top_expense_categories[1].total_spend == Decimal("7.00")`, `result.top_expense_categories[1].order_count == 1`.

### OOV-TE-02 — categories sorted by total descending and cut to limit
- **Rules:** `get_stats` R19
- **Kind:** happy
- **Expect:** pass

**Given**
1. eo `"EX-1"`, but `expense_category "department"`, `total_amount Decimal("10.00")`.
2. eo `"EX-2"`, but `expense_category "factory"`, `total_amount Decimal("30.00")`.
3. eo `"EX-3"`, but `total_amount Decimal("20.00")` (category "other").

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `cats == ["factory", "other"]`.

### OOV-TE-03 — expense days at both edges
- **Rules:** `get_stats` R2, R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. eo `"EX-A"`, but `expense_date PRE`, `total_amount Decimal("1.00")`.
2. eo `"EX-B"`, but `expense_date START`, `total_amount Decimal("10.00")`.
3. eo `"EX-C"`, but `expense_date END`, `total_amount Decimal("100.00")`.
4. eo `"EX-D"`, but `expense_date POST`, `total_amount Decimal("1000.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `cats == ["other"]`.
2. returns: `result.top_expense_categories[0].total_spend == Decimal("110.00")`, `result.top_expense_categories[0].order_count == 2`.

### OOV-TE-04 — a voided expense order counts in no category
- **Rules:** `get_stats` R19, R11a [BUG-2500]
- **Kind:** bug
- **Expect:** xfail BUG-2500
- **Fails today on:** Then 2 (the voided 300.00 is in "other")

**Given**
1. eo `"EX-1"`, but `total_amount Decimal("10.00")` (category "other").
2. voided eo `"EX-2"`, but `total_amount Decimal("300.00")` (category "other").
3. voided eo `"EX-3"`, but `expense_category "factory"`, `total_amount Decimal("5.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `"other" in cats`.
2. returns: `result.top_expense_categories[cats.index("other")].total_spend == Decimal("10.00")`, `result.top_expense_categories[cats.index("other")].order_count == 1`.
3. returns: `cats == ["other"]`.

### OOV-TE-05 — tied categories are ordered by category text
- **Rules:** `get_stats` R19a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (ties keep the query's row order; may hold by chance)

**Given**
1. eo `"EX-1"`, but `total_amount Decimal("5.00")` (category "other").
2. eo `"EX-2"`, but `expense_category "factory"`, `total_amount Decimal("5.00")`.
3. eo `"EX-3"`, but `expense_category "department"`, `total_amount Decimal("5.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=2)`.

**Then**
1. returns: `cats == ["department", "factory"]`.

### OOV-TE-06 — the categories' SQL cut orders by category text after the total
- **Rules:** `get_stats` R19, R19a [BUG-2505]
- **Kind:** bug
- **Expect:** xfail BUG-2505
- **Fails today on:** Then 3 (today the ORDER BY has the summed total only)

**Given**
1. eo `"EX-1"` (category "other", 10.00).
2. recorder around the When.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `cats == ["other"]`.
2. statement: `es = [s for s in stmts if "expense_orders" in s and "GROUP BY" in s and "LIMIT" in s and "expense_category" in s.split("GROUP BY")[-1]]`; `len(es) == 1`.
3. statement: `"expense_category" in order_part(es[0])`.

## `get_stats` — factory view (`factory_id`)

### OOV-FV-01 — PO and sales lines are kept only for the factory
- **Rules:** `get_stats` R5 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502
- **Fails today on:** Then 1 (the call raises InvalidRequestError: the customers' factory filter is added after LIMIT)

**Given**
1. p1 = po `"PO-1"` (storage F1); pol(p1, I1, Decimal("5.00"), Decimal("5.00")).
2. p2 = po `"PO-2"`, but `destination_id F2.id`; pol(p2, I2, Decimal("7.00"), Decimal("7.00")).
3. s1 = so `"SO-1"` (factory F1); sol(s1, I3, Decimal("2.00"), Decimal("2.00")).
4. IV = `Item(workspace_id=W1.id, name="Valve", name_normalized="valve", unit="pcs")`.
5. s2 = so `"SO-2"`, but `factory_id F2.id`; sol(s2, IV, Decimal("9.00"), Decimal("9.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F1.id, limit=10)`.

**Then**
1. returns: `sorted(item_ids) == sorted([I1.id, I3.id])`.

### OOV-FV-02 — a transfer between two factories counts in the destination's view
- **Rules:** `get_stats` R12 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502
- **Fails today on:** Then 1 (the call raises InvalidRequestError: the customers' factory filter is added after LIMIT)

**Given**
1. t1 = to `"TO-1"`, but `destination_location_type "machine"`, `destination_location_id M1.id` (source F2 storage); tol(t1, I1, Decimal("4.00")).
2. t2 = to `"TO-2"`, but `source_location_id FA.id`, `destination_location_id FA.id`; tol(t2, I2, Decimal("6.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F1.id, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.

### OOV-FV-03 — the same transfer counts in the source factory's view
- **Rules:** `get_stats` R12 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502
- **Fails today on:** Then 1 (the call raises InvalidRequestError: the customers' factory filter is added after LIMIT)

**Given**
1. t1 = to `"TO-1"`, but `destination_location_type "machine"`, `destination_location_id M1.id` (source F2 storage); tol(t1, I1, Decimal("4.00")).
2. t2 = to `"TO-2"`, but `source_location_id FA.id`, `destination_location_id FA.id`; tol(t2, I2, Decimal("6.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F2.id, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.

### OOV-FV-04 — vendors come from the factory's POs only; expense orders are not read
- **Rules:** `get_stats` R15 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502
- **Fails today on:** Then 1 (the call raises InvalidRequestError: the customers' factory filter is added after LIMIT)

**Given**
1. po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("10.00")` (storage F1).
2. po `"PO-2"`, but `account_id AC2.id`, `destination_id F2.id`, `total_amount Decimal("20.00")`.
3. eo `"EX-1"`, but `account_id AC3.id`, `expense_category "factory"`, `total_amount Decimal("30.00")`.
4. eo `"EX-2"`, but `account_id AC1.id`, `total_amount Decimal("40.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F1.id, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. returns: `vrow(AC1).total_spend == Decimal("10.00")`, `vrow(AC1).order_count == 1`.

### OOV-FV-05 — customers are filtered to the factory before the cut
- **Rules:** `get_stats` R18 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502
- **Fails today on:** Then 1 (the call raises InvalidRequestError: the factory filter is added after LIMIT)

**Given**
1. so `"SO-1"`, but `account_id AC2.id`, `factory_id F2.id`, `total_amount Decimal("100.00")`.
2. so `"SO-2"`, but `total_amount Decimal("10.00")` (AC1, factory F1).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F1.id, limit=1)`.

**Then**
1. returns: `customer_ids == [AC1.id]`.
2. returns: `crow(AC1).total_spend == Decimal("10.00")`, `crow(AC1).order_count == 1`.

### OOV-FV-06 — categories and factories are empty in a factory view
- **Rules:** `get_stats` R20, R21 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502
- **Fails today on:** Then 1 (the call raises InvalidRequestError: the customers' factory filter is added after LIMIT)

**Given**
1. eo `"EX-1"`, but `expense_category "factory"`, `total_amount Decimal("30.00")`.
2. po `"PO-1"`, but `total_amount Decimal("10.00")` (storage F1).
3. wo `"WO-1"` (factory F1).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F1.id, limit=10)`.

**Then**
1. returns: `result.top_expense_categories == []`.
2. returns: `result.top_factories == []`.

### OOV-FV-07 — a factory with no orders gives five empty lists
- **Rules:** `get_stats` R5, R12, R15, R18, R20, R21 [BUG-2502]; Errors row
- **Kind:** bug
- **Expect:** xfail BUG-2502
- **Fails today on:** Then 1 (the call raises InvalidRequestError, also for a factory with no orders)

**Given**
1. p1 = po `"PO-1"`, but `account_id AC1.id` (storage F1); pol(p1, I1, Decimal("1.00"), Decimal("1.00")).
2. so `"SO-1"` (factory F1).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=FA.id, limit=10)`.

**Then**
1. returns: `result.top_items == []`, `result.top_vendors == []`, `result.top_customers == []`.
2. returns: `result.top_expense_categories == []`, `result.top_factories == []`.

### OOV-FV-08 — a factory view on a W2 factory shows nothing of that workspace
- **Rules:** `_build_top_factories` R8b [BUG-2504]; `get_stats` R5, R12, R18 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502, BUG-2504 (passes only when both are fixed)
- **Fails today on:** Then 1 (the call raises InvalidRequestError: any `factory_id` fails today)

**Given**
1. p1 = po `"PO-1"`, but `destination_id F9.id`, `account_id AC1.id`; pol(p1, I1, Decimal("4.00"), Decimal("4.00")).
2. t1 = to `"TO-1"`, but `destination_location_id F9.id`; tol(t1, I2, Decimal("2.00")).
3. s1 = so `"SO-1"`, but `factory_id F9.id`; sol(s1, I3, Decimal("3.00"), Decimal("3.00")).
4. w1 = wo `"WO-1"`, but `factory_id F9.id`.
5. p2 = W2 po `"PO-2"`, but `account_id AC9.id`; pol(p2, I9, Decimal("5.00"), Decimal("5.00")).
6. s2 = W2 so `"SO-2"`; sol(s2, I9, Decimal("6.00"), Decimal("6.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F9.id, limit=10)`.

**Then**
1. returns: `result.top_items == []`, `result.top_vendors == []`, `result.top_customers == []`.
2. returns: `result.top_expense_categories == []`, `result.top_factories == []`.

### OOV-FV-09 — a factory view on a W0 factory shows nothing of that workspace
- **Rules:** `_build_top_factories` R8b [BUG-2504]; `get_stats` R5, R12, R18 [BUG-2502]
- **Kind:** bug
- **Expect:** xfail BUG-2502, BUG-2504 (passes only when both are fixed)
- **Fails today on:** Then 1 (the call raises InvalidRequestError: any `factory_id` fails today)

**Given**
1. p1 = po `"PO-1"`, but `destination_id F0.id`, `account_id AC1.id`; pol(p1, I1, Decimal("4.00"), Decimal("4.00")).
2. t1 = to `"TO-1"`, but `destination_location_id F0.id`; tol(t1, I2, Decimal("2.00")).
3. s1 = so `"SO-1"`, but `factory_id F0.id`; sol(s1, I3, Decimal("3.00"), Decimal("3.00")).
4. w1 = wo `"WO-1"`, but `factory_id F0.id`.
5. p2 = W0 po `"PO-2"`, but `account_id AC0.id`; pol(p2, I0, Decimal("5.00"), Decimal("5.00")).
6. s2 = W0 so `"SO-2"`; sol(s2, I0, Decimal("6.00"), Decimal("6.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, factory_id=F0.id, limit=10)`.

**Then**
1. returns: `result.top_items == []`, `result.top_vendors == []`, `result.top_customers == []`.
2. returns: `result.top_expense_categories == []`, `result.top_factories == []`.

## OQ-29 → BUG-2480 — committed / projected / total

> Owner answer 2026-11-10: each money measure is reported as committed, projected and their total; voided orders are in none (spec Money stage D1–D8). OQ29-01 … 04 and OQ29-15 hold before and after the fix (drafts still count in totals, counts and rankings) and are pass cards. OQ29-05 … 14, 16, 17 are strict xfail BUG-2480: they fail today on the first `…_committed` / `…_projected` field read.

### OOV-OQ29-01 — lines of a draft PO count in top items
- **Rules:** `get_stats` R4, Money stage D1, D8
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = draft po `"PO-1"`.
2. pol(p1, I1, Decimal("5.00"), Decimal("50.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).purchase_qty == Decimal("5.00")`, `irow(I1).total_spend == Decimal("50.00")`.

### OOV-OQ29-02 — a draft PO counts in its vendor's spend
- **Rules:** `get_stats` R11, R14, Money stage D1
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = draft po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("200000.00")`.
2. p2 = po `"PO-2"`, but `account_id AC2.id`, `total_amount Decimal("5.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id, AC2.id]`.
2. returns: `vrow(AC1).total_spend == Decimal("200000.00")`, `vrow(AC1).order_count == 1`.

### OOV-OQ29-03 — a draft sales order counts in top customers
- **Rules:** `get_stats` R16, Money stage D1, D8
- **Kind:** happy
- **Expect:** pass

**Given**
1. s1 = draft so `"SO-1"`, but `total_amount Decimal("70.00")` (AC1).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `customer_ids == [AC1.id]`.
2. returns: `crow(AC1).total_spend == Decimal("70.00")`, `crow(AC1).order_count == 1`.

### OOV-OQ29-04 — draft PO, sales and work orders each count for their factory
- **Rules:** `_build_top_factories` R2, R4, R5, R7, Money stage D8
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = draft po `"PO-1"`, but `total_amount Decimal("30.00")` (storage F1).
2. s1 = draft so `"SO-1"`, but `factory_id F2.id`, `total_amount Decimal("20.00")`.
3. w1 = draft wo `"WO-1"`, but `factory_id FA.id`, `cost Decimal("10.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `sorted(fids) == sorted([F1.id, F2.id, FA.id])`.
2. returns: `frow(F1).purchase_count == 1`, `frow(F2).sales_count == 1`, `frow(FA).work_count == 1`.

### OOV-OQ29-05 — an item's purchase spend is split across every PO stage path
- **Rules:** `get_stats` R4b [BUG-2480], Money stage D1, D3, D4
- **Kind:** bug
- **Expect:** xfail BUG-2480
- **Fails today on:** Then 3 (TopItemRow has no `total_spend_committed`)

**Given**
1. pR = po `"PO-R"`, but `current_status_id SR.id`; pol(pR, I1, Decimal("1.00"), Decimal("100.00")).
2. pC = po `"PO-C"`, but `current_status_id SC.id`; pol(pC, I1, Decimal("1.00"), Decimal("20.00")).
3. pA = draft po `"PO-A"`; pol(pA, I1, Decimal("1.00"), Decimal("5000.00")); poa(pA, U1), but approved; poa(pA, U2), but approved.
4. pD = draft po `"PO-D"`; pol(pD, I1, Decimal("1.00"), Decimal("3.00")).
5. pP = po `"PO-P"`, but `current_status_id SP.id`; pol(pP, I1, Decimal("1.00"), Decimal("0.40")).
6. pH = draft po `"PO-H"`; pol(pH, I1, Decimal("1.00"), Decimal("0.06")); poa(pH, U1), but approved; poa(pH, U2).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).total_spend == Decimal("5123.46")`, `irow(I1).line_count == 6`.
3. returns: `irow(I1).total_spend_committed == Decimal("5120.00")`.
4. returns: `str(irow(I1).total_spend_committed) == "5120.00"`.
5. returns: `irow(I1).total_spend_projected == Decimal("3.46")`.
6. returns: `str(irow(I1).total_spend_projected) == "3.46"`.

### OOV-OQ29-06 — voided POs are in none of an item's three spend figures
- **Rules:** `get_stats` R4a, R4b [BUG-2480], Money stage D2
- **Kind:** bug
- **Expect:** xfail BUG-2480, BUG-2500 (passes only when both are fixed)
- **Fails today on:** Then 2 (TopItemRow has no `total_spend_committed`)

**Given**
1. pR = po `"PO-R"`, but `current_status_id SR.id`; pol(pR, I1, Decimal("1.00"), Decimal("10.00")).
2. pV = voided po `"PO-V"`, but `current_status_id SR.id`; pol(pV, I1, Decimal("50.00"), Decimal("1000.00")).
3. pW = voided po `"PO-W"`, but `current_status_id SD.id`; pol(pW, I1, Decimal("9.00"), Decimal("7.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `I1.id in item_ids`.
2. returns: `irow(I1).total_spend_committed == Decimal("10.00")`.
3. returns: `irow(I1).total_spend_projected == Decimal("0")`.
4. returns: `irow(I1).total_spend == Decimal("10.00")`.
5. returns: `irow(I1).purchase_qty == Decimal("1.00")`.

### OOV-OQ29-07 — an item's sales revenue is split across every sales stage path
- **Rules:** `get_stats` R7a [BUG-2480], Money stage D1, D3, D5
- **Kind:** bug
- **Expect:** xfail BUG-2480, BUG-2481 (passes only when both are fixed)
- **Fails today on:** Then 3 (TopItemRow has no `sales_revenue_committed`)

**Given**
1. s1 = so `"SO-1"`, but `order_completed True`; sol(s1, I1, Decimal("1.00"), Decimal("300.00")).
2. s2 = so `"SO-2"`; sol(s2, I1, Decimal("1.00"), Decimal("40.00")); soa(s2, U1), but approved.
3. s3 = so `"SO-3"`; sol(s3, I1, Decimal("1.00"), Decimal("5.00")).
4. s4 = so `"SO-4"`; sol(s4, I1, Decimal("1.00"), Decimal("0.60")); soa(s4, U1), but approved; soa(s4, U2).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).sales_qty == Decimal("4.00")`, `irow(I1).line_count == 4`.
3. returns: `irow(I1).sales_revenue_committed == Decimal("340.00")`.
4. returns: `str(irow(I1).sales_revenue_committed) == "340.00"`.
5. returns: `irow(I1).sales_revenue_projected == Decimal("5.60")`.
6. returns: `irow(I1).sales_revenue == Decimal("345.60")`.

### OOV-OQ29-08 — a vendor's spend is split across PO and expense stage paths
- **Rules:** `get_stats` R11b [BUG-2480], Money stage D1, D3, D4, D6, D8
- **Kind:** bug
- **Expect:** xfail BUG-2480
- **Fails today on:** Then 4 (TopAccountRow has no `total_spend_committed`)

**Given**
1. po `"PO-R"`, but `account_id AC1.id`, `current_status_id SR.id`, `total_amount Decimal("100.00")`.
2. draft po `"PO-D"`, but `account_id AC1.id`, `total_amount Decimal("2.00")`.
3. eo `"EX-C"`, but `account_id AC1.id`, `completed_at T0`, `total_amount Decimal("30.00")`.
4. eo `"EX-Z"`, but `account_id AC1.id`, `required_approvals 0`, `total_amount Decimal("4.00")`.
5. e5 = eo `"EX-A"`, but `account_id AC1.id`, `total_amount Decimal("600.00")`; eoa(e5, U1), but approved.
6. eo `"EX-N"`, but `account_id AC1.id`, `total_amount Decimal("0.50")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. returns: `vrow(AC1).order_count == 6`.
3. returns: `vrow(AC1).total_spend == Decimal("736.50")`.
4. returns: `vrow(AC1).total_spend_committed == Decimal("734.00")`.
5. returns: `str(vrow(AC1).total_spend_committed) == "734.00"`.
6. returns: `vrow(AC1).total_spend_projected == Decimal("2.50")`.
7. returns: `str(vrow(AC1).total_spend_projected) == "2.50"`.

### OOV-OQ29-09 — expense approved_at is not the mark; required_approvals overrides the row count
- **Rules:** `get_stats` R11b [BUG-2480], Money stage D3, D6
- **Kind:** bug
- **Expect:** xfail BUG-2480
- **Fails today on:** Then 3 (TopAccountRow has no `total_spend_committed`)

**Given**
1. eo `"EX-1"`, but `account_id AC1.id`, `approved_at T0`, `approved_by U1.id`, `total_amount Decimal("9.00")`.
2. e2 = eo `"EX-2"`, but `account_id AC1.id`, `required_approvals 1`, `total_amount Decimal("1.00")`; eoa(e2, U1), but approved; eoa(e2, U2).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id]`.
2. returns: `vrow(AC1).total_spend == Decimal("10.00")`.
3. returns: `vrow(AC1).total_spend_committed == Decimal("1.00")`.
4. returns: `vrow(AC1).total_spend_projected == Decimal("9.00")`.

### OOV-OQ29-10 — a customer's total is split across every sales stage path
- **Rules:** `get_stats` R16a [BUG-2480], Money stage D1, D3, D5, D8
- **Kind:** bug
- **Expect:** xfail BUG-2480
- **Fails today on:** Then 4 (TopAccountRow has no `total_spend_committed`)

**Given**
1. so `"SO-1"`, but `order_completed True`, `total_amount Decimal("70.00")` (AC1).
2. s2 = so `"SO-2"`, but `total_amount Decimal("8.00")` (AC1); soa(s2, U1), but approved.
3. so `"SO-3"`, but `total_amount Decimal("0.25")` (AC1).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `customer_ids == [AC1.id]`.
2. returns: `crow(AC1).order_count == 3`.
3. returns: `crow(AC1).total_spend == Decimal("78.25")`.
4. returns: `crow(AC1).total_spend_committed == Decimal("78.00")`.
5. returns: `crow(AC1).total_spend_projected == Decimal("0.25")`.
6. returns: `str(crow(AC1).total_spend_projected) == "0.25"`.

### OOV-OQ29-11 — a category's total is split across every expense stage path
- **Rules:** `get_stats` R19b [BUG-2480], Money stage D1, D3, D6, D8
- **Kind:** bug
- **Expect:** xfail BUG-2480
- **Fails today on:** Then 4 (TopExpenseCategoryRow has no `total_spend_committed`)

**Given**
1. eo `"EX-C"`, but `completed_at T0`, `total_amount Decimal("10.00")` (category "other").
2. eo `"EX-N"`, but `total_amount Decimal("1.00")`.
3. e3 = eo `"EX-H"`, but `total_amount Decimal("0.10")`; eoa(e3, U1), but approved; eoa(e3, U2).
4. e4 = eo `"EX-R"`, but `required_approvals 1`, `total_amount Decimal("200.00")`; eoa(e4, U1), but approved; eoa(e4, U2).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `cats == ["other"]`.
2. returns: `erow("other").order_count == 4`.
3. returns: `erow("other").total_spend == Decimal("211.10")`.
4. returns: `erow("other").total_spend_committed == Decimal("210.00")`.
5. returns: `erow("other").total_spend_projected == Decimal("1.10")`.
6. returns: `str(erow("other").total_spend_projected) == "1.10"`.

### OOV-OQ29-12 — a factory's purchase spend, sales revenue and work cost are each split
- **Rules:** `_build_top_factories` R7a [BUG-2480], Money stage D1, D3, D4, D5, D7, D8
- **Kind:** bug
- **Expect:** xfail BUG-2480, BUG-2481 (passes only when both are fixed)
- **Fails today on:** Then 3 (TopFactoryRow has no `purchase_spend_committed`)

**Given**
1. po `"PO-R"`, but `current_status_id SR.id`, `total_amount Decimal("100.00")` (storage F1).
2. draft po `"PO-D"`, but `total_amount Decimal("2.00")` (storage F1).
3. so `"SO-C"`, but `order_completed True`, `total_amount Decimal("50.00")` (factory F1).
4. so `"SO-N"`, but `total_amount Decimal("5.00")` (factory F1).
5. wo `"WO-C"`, but `cost Decimal("7.00")` (COMPLETED, factory F1).
6. wo `"WO-I"`, but `status WorkOrderStatusEnum.IN_PROGRESS`, `cost Decimal("3.00")`.
7. draft wo `"WO-D"`, but `cost Decimal("0.50")`.
8. w8 = draft wo `"WO-A"`, but `cost Decimal("0.25")`; woa(w8, U1), but approved.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 8`.
3. returns: `frow(F1).purchase_spend_committed == Decimal("100.00")`.
4. returns: `frow(F1).purchase_spend_projected == Decimal("2.00")`, `frow(F1).purchase_spend == Decimal("102.00")`.
5. returns: `frow(F1).sales_revenue_committed == Decimal("50.00")`.
6. returns: `frow(F1).sales_revenue_projected == Decimal("5.00")`, `frow(F1).sales_revenue == Decimal("55.00")`.
7. returns: `frow(F1).work_cost_committed == Decimal("10.25")`.
8. returns: `frow(F1).work_cost_projected == Decimal("0.50")`, `frow(F1).work_cost == Decimal("10.75")`.
9. returns: `str(frow(F1).work_cost_committed) == "10.25"`.

### OOV-OQ29-13 — voided and deleted orders are in none of a factory's figures
- **Rules:** `_build_top_factories` R2a, R5a, R7a [BUG-2480], Money stage D2
- **Kind:** bug
- **Expect:** xfail BUG-2480, BUG-2481, BUG-2500, BUG-2501 (passes only when all four are fixed)
- **Fails today on:** Then 2 (TopFactoryRow has no `purchase_spend_committed`)

**Given**
1. po `"PO-R"`, but `current_status_id SR.id`, `total_amount Decimal("10.00")` (storage F1).
2. voided po `"PO-V"`, but `current_status_id SR.id`, `total_amount Decimal("1000.00")`.
3. voided po `"PO-W"`, but `current_status_id SD.id`, `total_amount Decimal("3.00")`.
4. wo `"WO-C"`, but `cost Decimal("1.00")` (COMPLETED, factory F1).
5. voided wo `"WO-V"`, but `cost Decimal("50.00")`.
6. deleted wo `"WO-X"`, but `cost Decimal("60.00")` (COMPLETED).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).purchase_spend_committed == Decimal("10.00")`.
3. returns: `frow(F1).purchase_spend_projected == Decimal("0")`.
4. returns: `frow(F1).work_cost_committed == Decimal("1.00")`.
5. returns: `frow(F1).work_cost_projected == Decimal("0")`.

### OOV-OQ29-14 — approver rows of W0 and W2 do not meet a W1 order's approvals
- **Rules:** `get_stats` R4b [BUG-2480], Money stage D3 (approvers scoped to the order's workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2480
- **Fails today on:** Then 3 (TopItemRow has no `total_spend_committed`)

**Given**
1. pA = draft po `"PO-A"`; pol(pA, I1, Decimal("1.00"), Decimal("1.00")); `PurchaseOrderApprover(workspace_id=W0.id, purchase_order_id=pA.id, user_id=U1.id, assigned_at=T0, approved=True, approved_at=T0)`.
2. pB = draft po `"PO-B"`; pol(pB, I1, Decimal("1.00"), Decimal("2.00")); `PurchaseOrderApprover(workspace_id=W2.id, purchase_order_id=pB.id, user_id=U1.id, assigned_at=T0, approved=True, approved_at=T0)`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).total_spend == Decimal("3.00")`.
3. returns: `irow(I1).total_spend_committed == Decimal("0")`.
4. returns: `irow(I1).total_spend_projected == Decimal("3.00")`.

### OOV-OQ29-15 — rankings use the total, projected money included
- **Rules:** `get_stats` R14, Money stage D1
- **Kind:** happy
- **Expect:** pass

**Given**
1. draft po `"PO-1"`, but `account_id AC1.id`, `total_amount Decimal("100.00")`.
2. po `"PO-2"`, but `account_id AC2.id`, `current_status_id SR.id`, `total_amount Decimal("50.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `vendor_ids == [AC1.id, AC2.id]`.
2. returns: `vrow(AC1).total_spend == Decimal("100.00")`.

### OOV-OQ29-16 — voided POs and expense orders are in none of a vendor's three figures
- **Rules:** `get_stats` R11a, R11b [BUG-2480], Money stage D2
- **Kind:** bug
- **Expect:** xfail BUG-2480, BUG-2500 (passes only when both are fixed)
- **Fails today on:** Then 2 (TopAccountRow has no `total_spend_committed`)

**Given**
1. po `"PO-R"`, but `account_id AC1.id`, `current_status_id SR.id`, `total_amount Decimal("10.00")`.
2. voided po `"PO-V"`, but `account_id AC1.id`, `current_status_id SR.id`, `total_amount Decimal("1000.00")`.
3. voided eo `"EX-V"`, but `account_id AC1.id`, `completed_at T0`, `total_amount Decimal("300.00")`.
4. voided eo `"EX-W"`, but `account_id AC1.id`, `total_amount Decimal("7.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `AC1.id in vendor_ids`.
2. returns: `vrow(AC1).total_spend_committed == Decimal("10.00")`.
3. returns: `vrow(AC1).total_spend_projected == Decimal("0")`.
4. returns: `vrow(AC1).total_spend == Decimal("10.00")`.

### OOV-OQ29-17 — voided expense orders are in none of a category's three figures
- **Rules:** `get_stats` R19, R19b [BUG-2480], Money stage D2
- **Kind:** bug
- **Expect:** xfail BUG-2480, BUG-2500 (passes only when both are fixed)
- **Fails today on:** Then 2 (TopExpenseCategoryRow has no `total_spend_committed`)

**Given**
1. eo `"EX-C"`, but `completed_at T0`, `total_amount Decimal("10.00")` (category "other").
2. voided eo `"EX-V"`, but `completed_at T0`, `total_amount Decimal("300.00")`.
3. voided eo `"EX-W"`, but `total_amount Decimal("7.00")`.

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `"other" in cats`.
2. returns: `erow("other").total_spend_committed == Decimal("10.00")`.
3. returns: `erow("other").total_spend_projected == Decimal("0")`.
4. returns: `erow("other").total_spend == Decimal("10.00")`.

## OQ-30 → BUG-2481 — purchase spend, sales revenue and work cost apart

> Owner answer 2026-11-10: spend counts purchases only, sales revenue is its own figure, transfers add to no money figure, items rank by purchased quantity; a factory row keeps purchase spend, sales revenue and work cost apart and `total_value` equals purchase spend. OQ30-04 … 06 hold before and after the fix (quantities and counts still add every kind) and are pass cards; the others are strict xfail BUG-2481.

### OOV-OQ30-01 — an item's spend is purchases only; sales go to sales_revenue
- **Rules:** `get_stats` R7a [BUG-2481], R6
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 5 (`total_spend` is 220.00: purchase subtotal plus sales line total)

**Given**
1. p1 = po `"PO-1"`; pol(p1, I1, Decimal("10.00"), Decimal("100.00")).
2. t1 = to `"TO-1"`; tol(t1, I1, Decimal("10.00")).
3. s1 = so `"SO-1"`; sol(s1, I1, Decimal("10.00"), Decimal("120.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).total_quantity == Decimal("30.00")`, `irow(I1).line_count == 3`.
3. returns: `irow(I1).purchase_qty == Decimal("10.00")`, `irow(I1).transfer_qty == Decimal("10.00")`.
4. returns: `irow(I1).sales_qty == Decimal("10.00")`.
5. returns: `irow(I1).total_spend == Decimal("100.00")`.
6. returns: `irow(I1).sales_revenue == Decimal("120.00")`.
7. returns: `str(irow(I1).sales_revenue) == "120.00"`.

### OOV-OQ30-02 — items are ranked by purchased quantity
- **Rules:** `get_stats` R9 [BUG-2481]
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 1 (I1 is first today on combined quantity 25 > 20)

**Given**
1. p1 = po `"PO-1"`; pol(p1, I1, Decimal("5.00"), Decimal("5.00")).
2. pol(p1, I2, Decimal("20.00"), Decimal("20.00")), but `line_number 2`.
3. s1 = so `"SO-1"`; sol(s1, I1, Decimal("20.00"), Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=1)`.

**Then**
1. returns: `item_ids == [I2.id]`.

### OOV-OQ30-03 — a factory keeps purchase spend, sales revenue and work cost apart
- **Rules:** `_build_top_factories` R7a [BUG-2481], R3
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 4 (`total_value` is 22005.00: PO + sales + work)

**Given**
1. po `"PO-1"`, but `total_amount Decimal("10000.00")` (storage F1).
2. so `"SO-1"`, but `total_amount Decimal("12000.00")` (factory F1).
3. wo `"WO-1"`, but `cost Decimal("5.00")` (factory F1).
4. to `"TO-1"` (F2 storage → F1 storage).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 4`.
3. returns: `frow(F1).purchase_count == 1`, `frow(F1).transfer_count == 1`, `frow(F1).sales_count == 1`, `frow(F1).work_count == 1`.
4. returns: `frow(F1).total_value == Decimal("10000.00")`.
5. returns: `frow(F1).purchase_spend == Decimal("10000.00")`.
6. returns: `frow(F1).sales_revenue == Decimal("12000.00")`.
7. returns: `frow(F1).work_cost == Decimal("5.00")`.

### OOV-OQ30-04 — factories are ranked by the order count of every kind
- **Rules:** `_build_top_factories` R7, R11, Money stage D8
- **Kind:** happy
- **Expect:** pass

**Given**
1. po `"PO-1"`, but `total_amount Decimal("1.00")` (storage F1).
2. so `"SO-1"`, but `total_amount Decimal("1.00")` (factory F1).
3. po `"PO-2"`, but `destination_id F2.id`, `total_amount Decimal("900.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id, F2.id]`.

### OOV-OQ30-05 — total_quantity adds purchase, transfer and sales quantities
- **Rules:** `get_stats` R7, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. p1 = po `"PO-1"`; pol(p1, I1, Decimal("10.00"), Decimal("100.00")).
2. t1 = to `"TO-1"`; tol(t1, I1, Decimal("2.50")).
3. s1 = so `"SO-1"`; sol(s1, I1, Decimal("0.25"), Decimal("120.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).total_quantity == Decimal("12.75")`, `irow(I1).line_count == 3`.
3. returns: `irow(I1).purchase_qty == Decimal("10.00")`, `irow(I1).transfer_qty == Decimal("2.50")`, `irow(I1).sales_qty == Decimal("0.25")`.

### OOV-OQ30-06 — a factory's counts add every order kind
- **Rules:** `_build_top_factories` R7, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. po `"PO-1"`, but `total_amount Decimal("10000.00")` (storage F1).
2. so `"SO-1"`, but `total_amount Decimal("12000.00")` (factory F1).
3. wo `"WO-1"`, but `cost Decimal("5.00")` (factory F1).
4. to `"TO-1"` (F2 storage → F1 storage).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 4`.
3. returns: `frow(F1).purchase_count == 1`, `frow(F1).transfer_count == 1`, `frow(F1).sales_count == 1`, `frow(F1).work_count == 1`.

### OOV-OQ30-07 — the money tie-break between factories is purchase spend
- **Rules:** `_build_top_factories` R11 [BUG-2481]
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 1 (F1 is first today on `total_value` 900.00 from its sales order)

**Given**
1. so `"SO-1"`, but `total_amount Decimal("900.00")` (factory F1).
2. po `"PO-2"`, but `destination_id F2.id`, `total_amount Decimal("5.00")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id, F1.id]`.

### OOV-OQ30-08 — the spec's example: a factory with approved and draft POs and a completed sale
- **Rules:** `_build_top_factories` R7a [BUG-2481, BUG-2480]
- **Kind:** bug
- **Expect:** xfail BUG-2481, BUG-2480 (passes only when both are fixed)
- **Fails today on:** Then 3 (`total_value` is 24000.00 today)

**Given**
1. po `"PO-1"`, but `current_status_id SR.id`, `total_amount Decimal("10000.00")` (storage F1).
2. draft po `"PO-2"`, but `total_amount Decimal("2000.00")` (storage F1).
3. so `"SO-1"`, but `order_completed True`, `total_amount Decimal("12000.00")` (factory F1).

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).order_count == 3`.
3. returns: `frow(F1).total_value == Decimal("12000.00")`.
4. returns: `frow(F1).purchase_spend == Decimal("12000.00")`.
5. returns: `frow(F1).purchase_spend_committed == Decimal("10000.00")`, `frow(F1).purchase_spend_projected == Decimal("2000.00")`.
6. returns: `frow(F1).sales_revenue == Decimal("12000.00")`, `frow(F1).sales_revenue_committed == Decimal("12000.00")`.
7. returns: `frow(F1).work_cost == Decimal("0")`.

### OOV-OQ30-09 — an item never purchased comes after any purchased item
- **Rules:** `get_stats` R9 [BUG-2481]
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 1 (I3 is first today on transferred quantity 500)

**Given**
1. t1 = to `"TO-1"`; tol(t1, I3, Decimal("500.00")).
2. p1 = po `"PO-1"`; pol(p1, I2, Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I2.id, I3.id]`.

### OOV-OQ30-10 — equal purchased quantity is broken by purchase spend only
- **Rules:** `get_stats` R9 [BUG-2481]
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 1 (I1 is first today on combined quantity 11 > 10)

**Given**
1. p1 = po `"PO-1"`; pol(p1, I1, Decimal("10.00"), Decimal("5.00")).
2. pol(p1, I2, Decimal("10.00"), Decimal("9.00")), but `line_number 2`.
3. s1 = so `"SO-1"`; sol(s1, I1, Decimal("1.00"), Decimal("900.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I2.id, I1.id]`.

### OOV-OQ30-11 — a sold-only item has no spend and its line total as sales revenue
- **Rules:** `get_stats` R7a [BUG-2481], R6
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 3 (`total_spend` is 300.00 today)

**Given**
1. s1 = so `"SO-1"`; sol(s1, I1, Decimal("3.00"), Decimal("300.00")).

**When**
- `result = svc.get_stats(db, workspace_id=W1.id, from_date=START, to_date=END, limit=10)`.

**Then**
1. returns: `item_ids == [I1.id]`.
2. returns: `irow(I1).sales_qty == Decimal("3.00")`.
3. returns: `irow(I1).total_spend == Decimal("0")`.
4. returns: `irow(I1).sales_revenue == Decimal("300.00")`.
5. returns: `str(irow(I1).sales_revenue) == "300.00"`.

### OOV-OQ30-12 — a sales order adds sales revenue, not total_value, to its factory
- **Rules:** `_build_top_factories` R4, R7a [BUG-2481]
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 3 (`total_value` is 30.05 today)

**Given**
1. s1 = so `"SO-1"`, but `factory_id F2.id`, `total_amount Decimal("30.05")`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F2.id]`.
2. returns: `frow(F2).sales_count == 1`.
3. returns: `frow(F2).total_value == Decimal("0")`.
4. returns: `frow(F2).sales_revenue == Decimal("30.05")`.
5. returns: `str(frow(F2).sales_revenue) == "30.05"`.

### OOV-OQ30-13 — work orders add work cost, not total_value; a missing cost adds 0
- **Rules:** `_build_top_factories` R5, R7a [BUG-2481]
- **Kind:** bug
- **Expect:** xfail BUG-2481
- **Fails today on:** Then 3 (`total_value` is 12.34 today)

**Given**
1. w1 = wo `"WO-1"`, but `cost Decimal("12.34")`.
2. w2 = wo `"WO-2"`, but `cost None`.

**When**
- `result = svc._build_top_factories(db, W1.id, START, END, 10)`.

**Then**
1. returns: `fids == [F1.id]`.
2. returns: `frow(F1).work_count == 2`.
3. returns: `frow(F1).total_value == Decimal("0")`.
4. returns: `frow(F1).work_cost == Decimal("12.34")`.
5. returns: `str(frow(F1).work_cost) == "12.34"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `limit` outside 1–10 → 422 (spec HR-7 note) | `GET /orders/overview/stats` endpoint | `limit=0` and `limit=11` refused with 422; `from_date`, `to_date` required |
| reuse of `_po_report_date`, `_in_date_range` (FU-2) | `item_summary_service` | its own voided / workspace handling |
| work order `created_at` uses the database clock (FU-1) | work order model / DAO | day of a work order created near midnight |

## Spec gaps
None. Gap 1 of revision 3 was closed in spec round 3 by `_build_top_factories` R8b (Gap log G8); G1–G7 of revision 1 in spec round 2; the verifier's empty-unit gap in spec round 4 (`get_stats` R8c, G9).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_dec` | R1 | OOV-D-01, OOV-D-05 |
| `_dec` | R2 | OOV-D-02, OOV-D-03, OOV-D-04, OOV-D-05 |
| `_dec` | Errors (`InvalidOperation`) | OOV-D-06 |
| `_po_report_date` | R1 | OOV-RD-01, OOV-RD-02, OOV-TF-10, OOV-TI-09, OOV-TV-06 |
| `_in_date_range` | R1 | OOV-RD-02, OOV-IR-01, OOV-IR-02, OOV-IR-03, OOV-GS-08 |
| `_filter_po_by_factory` | R1 | OOV-FP-01, OOV-FP-11 |
| `_filter_po_by_factory` | R2 | OOV-FP-02 |
| `_filter_po_by_factory` | R2a [BUG-2504] | OOV-FP-06 |
| `_filter_po_by_factory` | R3 [BUG-2503] | OOV-FP-07, OOV-FP-08, OOV-FP-09 |
| `_filter_po_by_factory` | R4 | OOV-FP-01, OOV-FP-02, OOV-FP-03, OOV-FP-10, OOV-FP-11 |
| `_filter_po_by_factory` | R5 | OOV-FP-04, OOV-FP-05 |
| `_filter_transfer_by_factory` | R1 | OOV-FT-01, OOV-FT-02, OOV-FT-03, OOV-FT-09 |
| `_filter_transfer_by_factory` | R2 [BUG-2503] | OOV-FT-04, OOV-FT-06 |
| `_filter_transfer_by_factory` | R2 [BUG-2504] | OOV-FT-07 |
| `_filter_transfer_by_factory` | R3 | OOV-FT-01, OOV-FT-02, OOV-FT-05, OOV-FT-08, OOV-FT-09 |
| `_factory_from_location` | R1 | OOV-TF-01, OOV-TF-02, OOV-TF-17 |
| `_factory_from_location` | R2 | OOV-TF-03, OOV-TF-04, OOV-TF-05, OOV-TF-36 |
| `_factory_from_location` | R2a [BUG-2504] | OOV-TF-28, OOV-TF-29 |
| `_factory_from_location` | R3 [BUG-2503] | OOV-TF-05, OOV-TF-30, OOV-TF-31, OOV-TF-32 |
| `_factory_from_location` | R4 | OOV-TF-03 |
| `_accumulate_factory` | Inputs (`factory_map` entry, returns `None`) | OOV-AF-01, OOV-AF-02 |
| `_accumulate_factory` | R1 | OOV-AF-01, OOV-AF-02, OOV-TF-03, OOV-TF-05, OOV-TF-17 |
| `_accumulate_factory` | R2 | OOV-AF-02, OOV-AF-03, OOV-AF-07, OOV-TF-01, OOV-TF-02, OOV-TF-35 |
| `_accumulate_factory` | R3 | OOV-AF-02, OOV-AF-03, OOV-AF-04, OOV-AF-05, OOV-AF-06, OOV-TF-01, OOV-TF-04, OOV-TF-06, OOV-TF-07 |
| `_build_top_factories` | R1 | OOV-TF-09, OOV-TF-10, OOV-TF-11, OOV-TF-12, OOV-TF-13 |
| `_build_top_factories` | R2 | OOV-TF-01, OOV-TF-02, OOV-TF-03, OOV-OQ29-04, OOV-TF-35 |
| `_build_top_factories` | R2a [BUG-2500] | OOV-TF-20, OOV-OQ29-13 |
| `_build_top_factories` | R3 | OOV-TF-04, OOV-TF-05, OOV-TF-32, OOV-OQ30-03, OOV-TF-36 |
| `_build_top_factories` | R4 | OOV-TF-06, OOV-OQ29-04, OOV-OQ30-12 |
| `_build_top_factories` | R5 | OOV-TF-07, OOV-OQ29-04, OOV-OQ30-13 |
| `_build_top_factories` | R5a [BUG-2500, BUG-2501] | OOV-TF-21, OOV-TF-22, OOV-OQ29-13 |
| `_build_top_factories` | R6 | OOV-TF-08 |
| `_build_top_factories` | R7 | OOV-OQ29-04, OOV-OQ30-04, OOV-OQ30-06 |
| `_build_top_factories` | R7a [BUG-2481, BUG-2480] | OOV-OQ29-12, OOV-OQ29-13, OOV-OQ30-03, OOV-OQ30-08, OOV-OQ30-12, OOV-OQ30-13 |
| `_build_top_factories` | R8 | OOV-TF-08, OOV-GS-01 |
| `_build_top_factories` | R8a [BUG-2504] | OOV-TF-23, OOV-TF-24, OOV-TF-25, OOV-TF-26, OOV-TF-27, OOV-TF-28 |
| `_build_top_factories` | R9 | OOV-TF-01, OOV-TF-16, OOV-TF-17 |
| `_build_top_factories` | R9a [BUG-2506] | OOV-TF-18, OOV-TF-19 |
| `_build_top_factories` | R10 | OOV-TF-01, OOV-TF-04, OOV-TF-06, OOV-TF-07, OOV-OQ30-06 |
| `_build_top_factories` | R11 | OOV-TF-14, OOV-TF-15, OOV-OQ30-04 |
| `_build_top_factories` | R11 [BUG-2481] (money tie-break = purchase spend) | OOV-OQ30-07 |
| `_build_top_factories` | R11a [BUG-2505] | OOV-TF-33, OOV-TF-34 |
| Money stage | D1 | OOV-OQ29-01 … OQ29-03, OOV-OQ29-05, OOV-OQ29-07, OOV-OQ29-08, OOV-OQ29-10, OOV-OQ29-11, OOV-OQ29-12, OOV-OQ29-15 |
| Money stage | D2 [BUG-2480] | OOV-OQ29-06, OOV-OQ29-13, OOV-OQ29-16, OOV-OQ29-17 |
| Money stage | D3 [BUG-2480] | OOV-OQ29-05, OOV-OQ29-07, OOV-OQ29-08, OOV-OQ29-09, OOV-OQ29-10, OOV-OQ29-11, OOV-OQ29-12, OOV-OQ29-14 |
| Money stage | D4 [BUG-2480] | OOV-OQ29-05, OOV-OQ29-08, OOV-OQ29-12, OOV-OQ30-08 |
| Money stage | D5 [BUG-2480] | OOV-OQ29-07, OOV-OQ29-10, OOV-OQ29-12, OOV-OQ30-08 |
| Money stage | D6 [BUG-2480] | OOV-OQ29-08, OOV-OQ29-09, OOV-OQ29-11 |
| Money stage | D7 [BUG-2480] | OOV-OQ29-12 |
| Money stage | D8 | OOV-OQ29-01, OOV-OQ29-03, OOV-OQ29-04, OOV-OQ29-08, OOV-OQ29-10, OOV-OQ29-11, OOV-OQ29-12, OOV-OQ30-04 |
| `get_stats` | Returns | OOV-GS-01 |
| `get_stats` | R1 | OOV-GS-02, OOV-GS-03, OOV-GS-04, OOV-GS-05, OOV-GS-06, OOV-GS-07 |
| `get_stats` | R2 (workspace, range) | OOV-GS-08, OOV-GS-09, OOV-GS-10, OOV-GS-15, OOV-TI-09, OOV-TI-10, OOV-TI-11, OOV-TV-06, OOV-TV-07, OOV-TC-04, OOV-TE-03 |
| `get_stats` | R2 (TC6: no commit / rollback, pending kept, error unchanged) | OOV-GS-11, OOV-GS-12, OOV-GS-13 |
| `get_stats` | Side effects none | OOV-GS-14 |
| `get_stats` | R3 | OOV-TI-01, OOV-TI-04, OOV-TI-05 |
| `get_stats` | R4 | OOV-TI-01, OOV-TI-02, OOV-TI-03, OOV-TI-09, OOV-OQ29-01, OOV-TI-21 |
| `get_stats` | R4a [BUG-2500] | OOV-TI-12, OOV-OQ29-06 |
| `get_stats` | R4b [BUG-2480] | OOV-OQ29-05, OOV-OQ29-06, OOV-OQ29-14 |
| `get_stats` | R5 [BUG-2502] | OOV-FV-01, OOV-FV-07, OOV-FV-08, OOV-FV-09 |
| `get_stats` | R6 | OOV-TI-02, OOV-TI-04, OOV-TI-05, OOV-TI-10, OOV-TI-11, OOV-OQ30-05, OOV-TI-18, OOV-TI-19 |
| `get_stats` | R6a [BUG-2504] | OOV-TI-13, OOV-TI-14, OOV-TI-15 |
| `get_stats` | R7 | OOV-OQ30-05 |
| `get_stats` | R7a [BUG-2481] | OOV-OQ29-07, OOV-OQ30-01, OOV-OQ30-11 |
| `get_stats` | R8 | OOV-TI-01, OOV-TI-06, OOV-TI-18, OOV-TI-19 |
| `get_stats` | R8c | OOV-TI-20 |
| `get_stats` | R9 | OOV-TI-07, OOV-TI-08, OOV-GS-06 |
| `get_stats` | R9 [BUG-2481] (rank by purchased quantity) | OOV-OQ30-02, OOV-OQ30-09, OOV-OQ30-10 |
| `get_stats` | R9a [BUG-2505] | OOV-TI-16, OOV-TI-17 |
| `get_stats` | R10 | OOV-TV-01, OOV-TV-02, OOV-TV-03, OOV-TV-06, OOV-TV-07, OOV-TV-14, OOV-TV-16, OOV-TV-17 |
| `get_stats` | R11 | OOV-OQ29-02 |
| `get_stats` | R11a [BUG-2500] | OOV-TV-08, OOV-TV-09, OOV-TE-04, OOV-OQ29-16 |
| `get_stats` | R11b [BUG-2480] | OOV-OQ29-08, OOV-OQ29-09, OOV-OQ29-16 |
| `get_stats` | R12 [BUG-2502] | OOV-FV-02, OOV-FV-03, OOV-FV-07, OOV-FV-08, OOV-FV-09 |
| `get_stats` | R13 | OOV-TV-01, OOV-TV-04, OOV-TV-15, OOV-TV-16 |
| `get_stats` | R13a [BUG-2504] | OOV-TV-10, OOV-TV-11 |
| `get_stats` | R14 | OOV-TV-05, OOV-GS-07, OOV-OQ29-02, OOV-OQ29-15 |
| `get_stats` | R14a [BUG-2505] | OOV-TV-12, OOV-TV-13 |
| `get_stats` | R15 [BUG-2502] | OOV-FV-04, OOV-FV-07 |
| `get_stats` | R16 | OOV-TC-01, OOV-TC-02, OOV-TC-04, OOV-OQ29-03, OOV-TC-08 |
| `get_stats` | R16 [BUG-2504] | OOV-TC-05 |
| `get_stats` | R16a [BUG-2480] | OOV-OQ29-10 |
| `get_stats` | R17 | OOV-TC-01, OOV-TC-03, OOV-GS-07 |
| `get_stats` | R17a [BUG-2505] | OOV-TC-06, OOV-TC-07 |
| `get_stats` | R18 [BUG-2502] | OOV-FV-05, OOV-FV-07, OOV-FV-08, OOV-FV-09 |
| `_build_top_factories` | R8b [BUG-2504] (factory view on another workspace's factory) | OOV-FV-08, OOV-FV-09 |
| `get_stats` | R19 | OOV-TE-01, OOV-TE-02, OOV-TE-03, OOV-TE-04, OOV-OQ29-17 |
| `get_stats` | R19a [BUG-2505] | OOV-TE-05, OOV-TE-06 |
| `get_stats` | R19b [BUG-2480] | OOV-OQ29-11, OOV-OQ29-17 |
| `get_stats` | R20 [BUG-2502] | OOV-FV-06, OOV-FV-07 |
| `get_stats` | R21 | OOV-GS-02, OOV-FV-06, OOV-FV-07 |
| `get_stats` | Errors (any `factory_id` raises today) [BUG-2502] | OOV-FV-01 … OOV-FV-07 (each fails today on that error) |
