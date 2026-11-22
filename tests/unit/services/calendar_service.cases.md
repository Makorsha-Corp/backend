# Test cases — `app/services/calendar_service.py`

> **Spec:** `tests/unit/services/calendar_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 6 (2026-11-04) — `calendar_service.verify.md` R3-1: CAL-OQ5-11 builds the caller's W2 `owner` and W0 `ground-team-manager` memberships before the W1 `ground-team` row (build order stated), so a membership read with `first()` and no workspace filter finds a privileged row and fails the card. No other card changed; counts unchanged.
> **Revision:** 5 (2026-11-04) — `calendar_service.verify.md` Round 2. R2-1: CAL-GE-12, CAL-GE-13 now give every row of the tie pairs an explicit id (**XID**), so the record expected first has the larger id in one pair and the smaller in the other. R2-2: new CAL-OQ5-08 … OQ5-11 (refused callers: private project with no creator; member of another project only; owner of another workspace only; privileged in other workspaces only; strict xfail BUG-1869). Conventions: XID, `os`. No card retired.
> **Revision:** 4 (2026-11-04) — (A) owner answers in the spec: OQ-5 → BUG-1869 (`get_events` gains required `user_id`; private project only for those who may open it), OQ-14 → BUG-1876, OQ-15 → BUG-1877, BUG-1878. Changed: CAL-OQ5-01 (now the refused caller, xfail BUG-1869), CAL-OQ14-01 (voided work order hidden, xfail BUG-1876), CAL-OQ14-02 (title; R3a; in-progress added; still pass), CAL-OQ15-01 (xfail BUG-1877), CAL-OQ15-02 (xfail BUG-1878). New: CAL-OQ5-02 … OQ5-07 (each allowed caller kind, and an inactive manager refused; xfail BUG-1869), CAL-WO-08, CAL-SO-06 (inactive factory hides nothing; pass). (B) `calendar_service.verify.md` findings 1–4: standing W0 built before W1 with its own rows; a W0 row added to WO-05, PO-07, EO-05, SO-04, SD-05, IN-05, PY-06, PB-05, PJ-07 and GE-20; PY-06 also gets a W2 payment on a W1 invoice; GE-12, GE-13 gain a second pair built in the opposite id order; new CAL-SD-07, CAL-PB-08 ("Cancelled" is not exactly "cancelled": listed). Conventions: W0 rows, `user_id` note, `WorkspaceMember`, `ProjectMember`. No card retired.
> **Revision:** 3 (2026-11-04) — executor note: Conventions state that `CalendarCategory` members are upper case (`CC.SALES`, not `CC.sales`); cards keep the lower-case spelling, read through that note. No card changed, added or retired.
> **Revision:** 2 (2026-11-04) — spec fill-gaps G1–G5 (`calendar_service.spec.md` Gap log). Changed: Conventions (row builders from the spec's minimum rows: `destination_id F1.id`, every amount an explicit two-place `Decimal`; closed states written as the spec's "What each close writes": **deleted** wo, **voided** po/eo, **voided** inv, **cancelled** batch, **deleted** proj; `ProjectStatusEnum` import), CAL-OQ5-01 (Given note: `invited_only` is now the spec's own value; card checked, assertions unchanged), CAL-PB-03 (the cancelled batch is a **cancelled** batch). New: CAL-PJ-12 (every project status listed, `meta.status` text, G4). Gaps 1–5 closed; none open. No card retired.
> **Counts:** 128 cases · 105 expected-to-pass · 23 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `_event_id` 1 · `_date_in_range` 6 · `_dt_to_date` 3 · `_category_allowed` 4 · `_expand_date_fields` 7 · `get_events` 21 (5 bug) · `_collect_work_orders` 8 + OQ 3 (2 bug) · `_collect_purchase_orders` 8 · `_collect_expense_orders` 6 · `_collect_sales_orders` 6 + OQ 1 (1 bug) · `_collect_sales_deliveries` 7 · `_collect_invoices` 8 · `_collect_invoice_payments` 8 (1 bug) · `_collect_production_batches` 8 (1 bug) · `_collect_projects` 12 (2 bug) + OQ 11 (11 bug, through `get_events`).
- **Depth:** full depth on the date filter, the category filter and workspace isolation (as asked); lighter elsewhere (read only, no money computed). Every date field of every collector has its own edge card: the day before `start`, `start`, `end`, the day after `end` (projects: 23:59:59.999999 before, 00:00 on `start`, 23:30 and 23:59:59.999999 on `end`, 00:00 after). Every collector has an "other category allowed → `[]`, no SQL sent" card and an isolation card whose `allowed` holds its own category, with other-workspace rows on both sides of the W1 row's id **and** of W1's workspace id (W0 before W1, W2 after).
- **Owner answers (OQ-5, OQ-14, OQ-15; 2026-11-04):** the cards keep their `OQ` IDs. Hidden by the answers, strict xfail: OQ5-01, OQ5-07 … OQ5-11 (refused callers), OQ14-01 (voided work order), OQ15-01, OQ15-02 (work and sales orders of a deleted factory). Shown, pass: OQ14-02 (draft, in-progress, completed), WO-08, SO-06 (inactive factory). OQ5-02 … OQ5-06 (each allowed caller kind) are xfail only because they pass the new `user_id`.
- **Expected-to-fail:** BUG-1805 5 (GE-17 … GE-21), BUG-1801 1 (PY-08), BUG-1807 1 (PB-07), BUG-1800 1 (PJ-10), BUG-1806 1 (PJ-11), BUG-1869 11 (OQ5-01 … OQ5-11), BUG-1876 1 (OQ14-01), BUG-1877 1 (OQ15-01), BUG-1878 1 (OQ15-02). All strict. Regression parts that hold today are pass cards: live payment (PY-01), batches of an inactive line or factory (PB-04), projects of an inactive factory (PJ-09).
- **Notable design choices:**
  - Collectors have no `ORDER BY` (spec Notes): their cards compare sorted `(record_id, date_label)` pairs, never list order, except for a single record's own events (field order, spec `get_events` R4).
  - Sort order (GE-10) is built so date, category value and title each decide one pair and ids do not rise with the expected order.
  - BUG-1869 cards go through `get_events` with `types=[CC.projects]` (the collector's new argument position is the fix's choice). Each allowed caller holds exactly one grant: the others are active `ground-team` members, so a test fails if a grant is checked wrongly.
  - GE-12, GE-13 give their tie pairs explicit ids (XID): the two rows of a pair come from different tables with separate sequences, so only explicit ids make the expected-first record larger in one pair and smaller in the other.
  - "Cancelled" (capital C) on a delivery or batch is not exactly `"cancelled"` and stays listed (SD-07, PB-08), as decided for R1.
  - PY-05 puts an active payment on a voided invoice: data the invoice manager would not produce, but R1 says the invoice's status is not looked at.
  - Row builders follow the spec's minimum rows (Facts). Every amount is set explicitly as a two-place `Decimal`, so `meta` amounts read `"10.50"` etc. whether or not the row was reloaded (spec "Amount text"). The `None` sides of amount, priority and project status are unreachable (NOT NULL, spec G2–G4) and get no card.
  - Closed rows carry every column the spec's "What each close writes" lists, though the calendar reads only the mark.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `CAL` = `app/services/calendar_service.py`. `ID` _event_id · `DR` _date_in_range · `DT` _dt_to_date · `CA` _category_allowed · `XF` _expand_date_fields · `GE` get_events · `WO` work orders · `PO` purchase · `EO` expense · `SO` sales orders · `SD` deliveries · `IN` invoices · `PY` payments · `PB` batches · `PJ` projects · `OQ5`, `OQ14`, `OQ15` = cards of that owner question (answered 2026-11-04).

**Imports.** `from app.services.calendar_service import CalendarService, calendar_service, _event_id, _date_in_range, _dt_to_date`; `CalendarCategory` as `CC` (its members are upper case: a card's `CC.sales`, `CC.work_orders` … means `CC.SALES`, `CC.WORK_ORDERS` …; the values are the lower-case texts), `CalendarEventResponse` (`app.schemas.calendar`). Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `work_order_type.WorkOrderType`, `work_order.WorkOrder`, `account.Account`, `account_invoice.AccountInvoice`, `invoice_payment.InvoicePayment`, `purchase_order.PurchaseOrder`, `expense_order.ExpenseOrder`, `sales_order.SalesOrder`, `sales_delivery.SalesDelivery`, `status.Status`, `production_line.ProductionLine`, `production_batch.ProductionBatch`, `machine.Machine`, `machine_maintenance_log.MachineMaintenanceLog`, `workspace_member.WorkspaceMember`, `project_member.ProjectMember`. `WorkOrderStatusEnum`, `WorkOrderPriorityEnum`, `ProjectStatusEnum`, `ProjectVisibilityEnum`, `MaintenanceTypeEnum` (`app.models.enums`). `ValidationError` (`pydantic`); `Decimal`; `date`, `datetime`, `timedelta`, `timezone`; `SimpleNamespace`; `patch`; `event` (`sqlalchemy`); `os`.

**Fixed values.** `svc` = `calendar_service`. START = `date(2026, 5, 1)`, END = `date(2026, 5, 31)`, PRE = `date(2026, 4, 30)`, POST = `date(2026, 6, 1)`, MID = `date(2026, 5, 10)`, FAR = `date(2025, 1, 1)`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. MISSING = `999999999`. `result` = what the When returns. Collector calls are positional: `svc._collect_x(db, W1.id, START, END, allowed)`.

**`user_id` (BUG-1869).** `get_events` has no `user_id` today. Only the OQ5 cards pass it (and are strict xfail: the call raises `TypeError` today). Every other `get_events` card keeps today's call; when the fix lands each gains `user_id=U1.id` (U1 is a project's creator nowhere, and no card but OQ5 builds a private project), with no other change.

**Standing rows** (every test, no Given line; built in this order, each flushed): W0, W1, W2 = `make_workspace(db)`, in that order (so `W0.id < W1.id < W2.id`); U1 = `make_profile(db)`.
- W0 rows: F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`; WT0 = `WorkOrderType(workspace_id=W0.id, name="Repair")`; AC0 = `Account(workspace_id=W0.id, name="Zero Co")`; S0 = `Status(workspace_id=W0.id, name="Draft", comment="Stage")`; L0 = `ProductionLine(workspace_id=W0.id, factory_id=F0.id, name="Zero Line")`; M0 = `Machine(workspace_id=W0.id, factory_id=F0.id, name="Zero Press")`.
- F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. FD = F1 but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`. FI = F1 but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False`. F9 = F1 but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`.
- WT1 = `WorkOrderType(workspace_id=W1.id, name="Repair")`; WT9 = the same in W2. AC1 = `Account(workspace_id=W1.id, name="Acme")`; AC9 = `Account(workspace_id=W2.id, name="Far Co")`. S1 = `Status(workspace_id=W1.id, name="Draft", comment="Stage")`; S9 = the same in W2.
- L1 = `ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Line One")`. LI = L1 but `name "Off Line"`, `is_active False`. LFI = L1 but `factory_id FI.id`, `name "Idle Line"`. LD = L1 but `factory_id FD.id`, `name "Lost Line"`. L9 = `ProductionLine(workspace_id=W2.id, factory_id=F9.id, name="Far Line")`.
- M1 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 1")`. MD = M1 but `name "Press 4"`, `is_active False`, `is_deleted True`. MF = M1 but `factory_id FD.id`, `name "Lost Press"`. M9 = `Machine(workspace_id=W2.id, factory_id=F9.id, name="Far Press")`.
- SOX = **so** `sales_order_number "SO-X"`, `order_date FAR`. SOX9 = **W2 so** `sales_order_number "SO-X9"`, `order_date FAR`. INX = **inv** `invoice_number "INV-X"`, `invoice_date FAR`. INX9 = **W2 inv** `invoice_number "INV-X9"`, `invoice_date FAR`. SOX0 = **W0 so** `sales_order_number "SO-X0"`, `order_date FAR`. INX0 = **W0 inv** `invoice_number "INV-X0"`, `invoice_date FAR`.

**Given rows.** Built directly, flushed one at a time in the order written (ids rise in that order). The card gives the number column and dates; every date column not named is `None`. "W2 x" = builder x with its W2 values. "W0 x" = builder x with every W2 value replaced by its W0 counterpart (W2 → W0, F9 → F0, WT9 → WT0, AC9 → AC0, S9 → S0, L9 → L0, M9 → M0, SOX9 → SOX0, INX9 → INX0). After "but" the card lists every other column that differs.
- **wo** = `WorkOrder(workspace_id=W1.id, work_order_number=…, title="Fix press", factory_id=F1.id, work_order_type_id=WT1.id, created_by=U1.id)`; W2: `workspace_id W2.id`, `factory_id F9.id`, `work_order_type_id WT9.id`. **deleted** wo = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **po** = `PurchaseOrder(workspace_id=W1.id, po_number=…, destination_type="storage", destination_id=F1.id, subtotal=Decimal("0.00"), total_amount=Decimal("10.50"), current_status_id=S1.id, created_by=U1.id, description="Steel order")`; W2: `workspace_id W2.id`, `current_status_id S9.id`. **voided** po/eo = `voided True`, `void_note "Void"`, `voided_at T0`, `voided_by U1.id`.
- **eo** = `ExpenseOrder(workspace_id=W1.id, expense_number=…, expense_category="other", expense_date=…, subtotal=Decimal("0.00"), total_amount=Decimal("20.00"), created_by=U1.id, description="Power bill")`; W2: `workspace_id W2.id`.
- **so** = `SalesOrder(workspace_id=W1.id, sales_order_number=…, account_id=AC1.id, factory_id=F1.id, order_date=…, total_amount=Decimal("30.00"), current_status_id=S1.id, created_by=U1.id, description="Chairs")`; W2: `workspace_id W2.id`, `account_id AC9.id`, `factory_id F9.id`, `current_status_id S9.id`.
- **dl** = `SalesDelivery(workspace_id=W1.id, sales_order_id=SOX.id, delivery_number=…, delivery_status="planned", created_by=U1.id)`; W2: `workspace_id W2.id`, `sales_order_id SOX9.id`.
- **inv** = `AccountInvoice(workspace_id=W1.id, account_id=AC1.id, invoice_number=…, invoice_type="payable", invoice_status="confirmed", invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), invoice_date=…, payment_status="unpaid", allow_payments=True, description="May rent")`; W2: `workspace_id W2.id`, `account_id AC9.id`. **voided** inv = `invoice_status "voided"`, `void_note "Void"`, `paid_amount Decimal("0.00")`, `payment_status "unpaid"`.
- **pay** = `InvoicePayment(workspace_id=W1.id, invoice_id=INX.id, payment_amount=Decimal("40.00"), payment_date=…, payment_method="cash", created_by=U1.id)`; W2: `workspace_id W2.id`, `invoice_id INX9.id`. **voided** pay = `is_voided True`, `voided_at T0`, `voided_by U1.id`, `void_note "manual void"`.
- **batch** = `ProductionBatch(workspace_id=W1.id, batch_number=…, production_line_id=L1.id, batch_date=…, status="draft", notes="Run A")`; W2: `workspace_id W2.id`, `production_line_id L9.id`. **cancelled** batch = `status "cancelled"`, `updated_by U1.id`.
- **proj** = `Project(workspace_id=W1.id, factory_id=F1.id, name=…, description="Main")` (naive datetimes; `status` left to its default `PLANNING`); W2: `workspace_id W2.id`, `factory_id F9.id`. **deleted** proj = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (`is_active` untouched).
- **log** = `MachineMaintenanceLog(workspace_id=W1.id, machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=…, summary="Bearing change")`; W2: `workspace_id W2.id`, `machine_id M9.id`. **gone** log = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.

**Named checks.**
- **keys(evs)** = `sorted((e.record_id, e.date_label) for e in evs)`. **recs(evs)** = `sorted({e.record_id for e in evs})`. **types_of(evs)** = `{e.source_type for e in evs}`. **of(src)** = `[e for e in result if e.source_type == src]`.
- **recorder** = a Given step: `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `statement`; removed with `event.remove` right after the When. `statement:` lines check `stmts`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing query** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "query", side_effect=E):` around the When.
- **commit point** = `db.commit()` after the Given lines above it (a savepoint release under the `db` fixture); lines marked "(after the commit point)" run after it, unflushed unless they say so.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call. `session:` lines check `db` directly, before anything expires it.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`. Write the call and checks as shown.

**XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k` — an explicit row id, unique per test process (no sequence gives it; no other row uses it). A Given row written "`id XID(k)`" passes `id=XID(k)` to its builder.

**Access rows (OQ5 cards).** **member(U, role, status="active")** = `WorkspaceMember(workspace_id=W1.id, user_id=U.id, role=role, status=status)`. **private proj** = proj, but `visibility ProjectVisibilityEnum.INVITED_ONLY`. **project member(P, U)** = `ProjectMember(workspace_id=W1.id, project_id=P.id, user_id=U.id)`.

**Race simulations.** None.

## `_event_id`

### CAL-ID-01 — the id is source:record:field
- **Rules:** `_event_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _event_id("project", 5, "deadline")`.

**Then**
1. returns: `result == "project:5:deadline"`.

## `_date_in_range`

### CAL-DR-01 — a day inside the range is in
- **Rules:** `_date_in_range` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _date_in_range(MID, START, END)`.

**Then**
1. returns: `result is True`.

### CAL-DR-02 — start itself is in
- **Rules:** `_date_in_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _date_in_range(START, START, END)`.

**Then**
1. returns: `result is True`.

### CAL-DR-03 — end itself is in
- **Rules:** `_date_in_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _date_in_range(END, START, END)`.

**Then**
1. returns: `result is True`.

### CAL-DR-04 — the day before start is out
- **Rules:** `_date_in_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _date_in_range(PRE, START, END)`.

**Then**
1. returns: `result is False`.

### CAL-DR-05 — the day after end is out
- **Rules:** `_date_in_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _date_in_range(POST, START, END)`.

**Then**
1. returns: `result is False`.

### CAL-DR-06 — None is out
- **Rules:** `_date_in_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _date_in_range(None, START, END)`.

**Then**
1. returns: `result is False`.

## `_dt_to_date`

### CAL-DT-01 — a datetime gives its calendar date, the last microsecond included
- **Rules:** `_dt_to_date` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dt_to_date(datetime(2026, 5, 31, 23, 59, 59, 999999))`.

**Then**
1. returns: `result == date(2026, 5, 31)`.
2. returns: `type(result) is date`.

### CAL-DT-02 — None gives None
- **Rules:** `_dt_to_date` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dt_to_date(None)`.

**Then**
1. returns: `result is None`.

### CAL-DT-03 — an aware datetime keeps its own calendar date (no conversion to UTC)
- **Rules:** `_dt_to_date` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `v = datetime(2026, 6, 1, 1, 30, tzinfo=timezone(timedelta(hours=6)))` (in UTC this is 2026-05-31 19:30).

**When**
- `result = _dt_to_date(v)`.

**Then**
1. returns: `result == date(2026, 6, 1)`.

## `CalendarService._category_allowed`

### CAL-CA-01 — no filter allows every category
- **Rules:** `_category_allowed` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._category_allowed(CC.sales, None)`.

**Then**
1. returns: `result is True`.

### CAL-CA-02 — a listed category is allowed
- **Rules:** `_category_allowed` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._category_allowed(CC.sales, {CC.purchase, CC.sales})`.

**Then**
1. returns: `result is True`.

### CAL-CA-03 — a category not listed is not allowed
- **Rules:** `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._category_allowed(CC.sales, {CC.purchase})`.

**Then**
1. returns: `result is False`.

### CAL-CA-04 — an empty set allows nothing
- **Rules:** `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._category_allowed(CC.sales, set())`.

**Then**
1. returns: `result is False`.

## `CalendarService._expand_date_fields`

### CAL-XF-01 — one event per in-range field, in field order, every field set
- **Rules:** `_expand_date_fields` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `R = SimpleNamespace(id=42, x_date=date(2026, 5, 20), y_date=date(2026, 5, 5))`.

**When**
- `result = svc._expand_date_fields(record=R, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date"), ("y_date", "Y date")], title="T-1", subtitle="Sub", link="/t", start=START, end=END, meta={"k": 1})`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `isinstance(result[0], CalendarEventResponse)`.
3. returns: `result[0].id == "thing:42:x_date"`, `result[0].category == CC.projects`, `result[0].source_type == "thing"`, `result[0].record_id == 42`.
4. returns: `result[0].date == date(2026, 5, 20)`, `result[0].date_label == "X date"`.
5. returns: `result[0].title == "T-1"`, `result[0].subtitle == "Sub"`, `result[0].link == "/t"`, `result[0].meta == {"k": 1}`.
6. returns: `result[1].id == "thing:42:y_date"`, `result[1].date == date(2026, 5, 5)`, `result[1].date_label == "Y date"`.

### CAL-XF-02 — a field the record does not have counts as None
- **Rules:** `_expand_date_fields` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = SimpleNamespace(id=43, x_date=MID)`.

**When**
- `result = svc._expand_date_fields(record=R, source_type="thing", category=CC.projects, date_fields=[("nope", "Nope"), ("x_date", "X date")], title="T-2", subtitle=None, link="/t", start=START, end=END)`.

**Then**
1. returns: `[e.date_label for e in result] == ["X date"]`.

### CAL-XF-03 — a datetime value is reduced to its date
- **Rules:** `_expand_date_fields` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = SimpleNamespace(id=44, x_date=datetime(2026, 5, 31, 23, 30))`.

**When**
- `result = svc._expand_date_fields(record=R, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date")], title="T-3", subtitle=None, link="/t", start=START, end=END)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].date == date(2026, 5, 31)`.

### CAL-XF-04 — None and out-of-range values give no event; both edges give one
- **Rules:** `_expand_date_fields` R2; `_date_in_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = SimpleNamespace(id=45, a=PRE, b=START, c=END, d=POST, e=None)`.

**When**
- `result = svc._expand_date_fields(record=R, source_type="thing", category=CC.projects, date_fields=[("a", "A"), ("b", "B"), ("c", "C"), ("d", "D"), ("e", "E")], title="T-4", subtitle=None, link="/t", start=START, end=END)`.

**Then**
1. returns: `[e.date_label for e in result] == ["B", "C"]`.

### CAL-XF-05 — no meta gives an empty dict
- **Rules:** `_expand_date_fields` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = SimpleNamespace(id=46, x_date=MID)`.

**When**
- `result = svc._expand_date_fields(record=R, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date")], title="T-5", subtitle=None, link="/t", start=START, end=END)`.

**Then**
1. returns: `result[0].meta == {}`.
2. returns: `result[0].subtitle is None`.

### CAL-XF-06 — two fields on the same day give two events
- **Rules:** `_expand_date_fields` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = SimpleNamespace(id=47, x_date=MID, y_date=MID)`.

**When**
- `result = svc._expand_date_fields(record=R, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date"), ("y_date", "Y date")], title="T-6", subtitle=None, link="/t", start=START, end=END)`.

**Then**
1. returns: `[e.id for e in result] == ["thing:47:x_date", "thing:47:y_date"]`.

### CAL-XF-07 — a title that is not a string is refused
- **Rules:** `_expand_date_fields` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `R = SimpleNamespace(id=48, x_date=MID)`.

**When**
- `svc._expand_date_fields(record=R, source_type="thing", category=CC.projects, date_fields=[("x_date", "X date")], title=None, subtitle=None, link="/t", start=START, end=END)`.

**Then**
1. raises: `ValidationError`.

## `CalendarService.get_events`

### CAL-GE-01 — start after end is refused before anything is read
- **Rules:** `get_events` R1; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = inv `invoice_number "INV-1"`, `invoice_date MID`.
2. recorder.

**When**
- `svc.get_events(db, workspace_id=W1.id, start=date(2026, 5, 2), end=date(2026, 5, 1))`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "start must be on or before end"`.
3. statement: `stmts == []`.

### CAL-GE-02 — start equal to end is a one-day range
- **Rules:** `get_events` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = inv `invoice_number "INV-1"`, `invoice_date date(2026, 5, 9)`.
2. A2 = inv `invoice_number "INV-2"`, `invoice_date MID`.
3. A3 = inv `invoice_number "INV-3"`, `invoice_date date(2026, 5, 11)`.
4. P = proj `name "Refit"`, `deadline datetime(2026, 5, 10, 23, 59, 59)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=MID, end=MID)`.

**Then**
1. returns: `keys(of("account_invoice")) == [(A2.id, "Invoice date")]`.
2. returns: `keys(of("project")) == [(P.id, "Deadline")]`.
3. returns: `len(result) == 2`.

### CAL-GE-03 — both edges of the range are included, the days outside are not
- **Rules:** `get_events` R3, R5; `_collect_invoices` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = inv `invoice_number "INV-1"`, `invoice_date PRE`.
2. A2 = inv `invoice_number "INV-2"`, `invoice_date START`.
3. A3 = inv `invoice_number "INV-3"`, `invoice_date END`.
4. A4 = inv `invoice_number "INV-4"`, `invoice_date POST`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Invoice date"), (A3.id, "Invoice date")]`.

### CAL-GE-04 — types=None gives every category, sales orders and deliveries, invoices and payments
- **Rules:** `get_events` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. wo `work_order_number "WO-1"`, `planned_date MID`.
2. po `po_number "PO-1"`, `order_date MID`.
3. eo `expense_number "EXP-1"`, `expense_date MID`.
4. so `sales_order_number "SO-1"`, `order_date MID`.
5. dl `delivery_number "SD-1"`, `scheduled_date MID`.
6. inv `invoice_number "INV-1"`, `invoice_date MID`.
7. pay `payment_date MID`.
8. batch `batch_number "B-1"`, `batch_date MID`.
9. proj `name "Refit"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=None)`.

**Then**
1. returns: `types_of(result) == {"work_order", "purchase_order", "expense_order", "sales_order", "sales_delivery", "account_invoice", "invoice_payment", "production_batch", "project"}`.
2. returns: `len(result) == 9`.
3. returns: `{e.category for e in result} == {CC.work_orders, CC.purchase, CC.expense, CC.sales, CC.invoices, CC.production, CC.projects}`.

### CAL-GE-05 — types=[] gives every category too
- **Rules:** `get_events` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. wo `work_order_number "WO-1"`, `planned_date MID`.
2. po `po_number "PO-1"`, `order_date MID`.
3. eo `expense_number "EXP-1"`, `expense_date MID`.
4. so `sales_order_number "SO-1"`, `order_date MID`.
5. dl `delivery_number "SD-1"`, `scheduled_date MID`.
6. inv `invoice_number "INV-1"`, `invoice_date MID`.
7. pay `payment_date MID`.
8. batch `batch_number "B-1"`, `batch_date MID`.
9. proj `name "Refit"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[])`.

**Then**
1. returns: `types_of(result) == {"work_order", "purchase_order", "expense_order", "sales_order", "sales_delivery", "account_invoice", "invoice_payment", "production_batch", "project"}`.
2. returns: `len(result) == 9`.

### CAL-GE-06 — types=[purchase] gives purchase orders only
- **Rules:** `get_events` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. wo `work_order_number "WO-1"`, `planned_date MID`.
2. P = po `po_number "PO-1"`, `order_date MID`.
3. eo `expense_number "EXP-1"`, `expense_date MID`.
4. so `sales_order_number "SO-1"`, `order_date MID`.
5. inv `invoice_number "INV-1"`, `invoice_date MID`.
6. proj `name "Refit"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.purchase])`.

**Then**
1. returns: `types_of(result) == {"purchase_order"}`.
2. returns: `keys(result) == [(P.id, "Order date")]`.

### CAL-GE-07 — types=[sales] gives sales orders and deliveries only
- **Rules:** `get_events` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. po `po_number "PO-1"`, `order_date MID`.
2. S = so `sales_order_number "SO-1"`, `order_date MID`.
3. D = dl `delivery_number "SD-1"`, `scheduled_date MID`.
4. inv `invoice_number "INV-1"`, `invoice_date MID`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.sales])`.

**Then**
1. returns: `types_of(result) == {"sales_order", "sales_delivery"}`.
2. returns: `len(result) == 2`.

### CAL-GE-08 — types=[invoices] gives invoices and payments only
- **Rules:** `get_events` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. so `sales_order_number "SO-1"`, `order_date MID`.
2. I = inv `invoice_number "INV-1"`, `invoice_date MID`.
3. Y = pay `payment_date MID`.
4. batch `batch_number "B-1"`, `batch_date MID`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.invoices])`.

**Then**
1. returns: `types_of(result) == {"account_invoice", "invoice_payment"}`.
2. returns: `len(result) == 2`.

### CAL-GE-09 — two categories, one listed twice: each event once
- **Rules:** `get_events` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. wo `work_order_number "WO-1"`, `planned_date MID`.
2. po `po_number "PO-1"`, `order_date MID`.
3. eo `expense_number "EXP-1"`, `expense_date MID`.
4. proj `name "Refit"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.purchase, CC.projects, CC.purchase])`.

**Then**
1. returns: `types_of(result) == {"purchase_order", "project"}`.
2. returns: `len(result) == 2`.

### CAL-GE-10 — sorted by date, then category value as text, then title
- **Rules:** `get_events` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. J = proj `name "Alpha"`, `start_date datetime(2026, 5, 10, 8, 0)`.
2. I = inv `invoice_number "INV-Z"`, `invoice_date MID`.
3. O = wo `work_order_number "WO-A"`, `planned_date MID`.
4. P2 = po `po_number "PO-B"`, `order_date MID`.
5. P1 = po `po_number "PO-A"`, `order_date MID`.
6. E = eo `expense_number "EXP-Y"`, `expense_date MID`.
7. B = batch `batch_number "B-1"`, `batch_date MID`.
8. S = so `sales_order_number "SO-1"`, `order_date MID`.
9. Z = wo `work_order_number "WO-Z"`, `planned_date date(2026, 5, 9)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[(e.source_type, e.record_id) for e in result] == [("work_order", Z.id), ("expense_order", E.id), ("account_invoice", I.id), ("production_batch", B.id), ("project", J.id), ("purchase_order", P1.id), ("purchase_order", P2.id), ("sales_order", S.id), ("work_order", O.id)]`.

### CAL-GE-11 — one record's two events on the same day keep field order
- **Rules:** `get_events` R4; `_collect_invoices` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = inv `invoice_number "INV-1"`, `invoice_date MID`, `due_date MID`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[e.date_label for e in result] == ["Invoice date", "Due date"]`.

### CAL-GE-12 — same date and title: the sales order comes before the delivery, whichever id is larger
- **Rules:** `get_events` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. D = dl `delivery_number "S-100"`, `scheduled_date MID`, but `id XID(1)`.
2. S = so `sales_order_number "S-100"`, `order_date MID`, but `id XID(2)`.
3. S2 = so `sales_order_number "S-200"`, `order_date date(2026, 5, 11)`, but `id XID(3)`.
4. D2 = dl `delivery_number "S-200"`, `scheduled_date date(2026, 5, 11)`, but `id XID(4)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.sales])`.

**Then**
1. returns: `[(e.source_type, e.record_id) for e in result] == [("sales_order", XID(2)), ("sales_delivery", XID(1)), ("sales_order", XID(3)), ("sales_delivery", XID(4))]`.

### CAL-GE-13 — same date and title: the invoice comes before the payment, whichever id is larger
- **Rules:** `get_events` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Y = pay `payment_date MID`, but `id XID(5)`.
2. I = inv `invoice_number f"Payment #{XID(5)}"`, `invoice_date MID`, but `id XID(6)`.
3. I2 = inv `invoice_number f"Payment #{XID(8)}"`, `invoice_date date(2026, 5, 11)`, but `id XID(7)`.
4. Y2 = pay `payment_date date(2026, 5, 11)`, but `id XID(8)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.invoices])`.

**Then**
1. returns: `[(e.source_type, e.record_id) for e in result] == [("account_invoice", XID(6)), ("invoice_payment", XID(5)), ("account_invoice", XID(7)), ("invoice_payment", XID(8))]`.

### CAL-GE-14 — a read: no commit, no rollback, the caller's pending changes stay pending
- **Rules:** `get_events` R5; TC6 (`base_service.spec.md`)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K = inv `invoice_number "INV-1"`, `invoice_date MID`.
2. commit point.
3. `K.description = "Edited"` (after the commit point; not flushed).
4. `N = Account(workspace_id=W1.id, name="Pending")`, `db.add(N)` (after the commit point; not flushed).

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END)`, inside **spies**.

**Then**
1. session: `K in db.dirty`.
2. session: `len(db.dirty) == 1`.
3. session: `len(db.new) == 1`.
4. session: `not db.deleted`.
5. mock called: `cm.call_count == 0`.
6. mock called: `rb.call_count == 0`.
7. returns: `recs(result) == [K.id]`.

### CAL-GE-15 — nothing in range for this workspace gives []
- **Rules:** `get_events` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. inv `invoice_number "INV-1"`, `invoice_date FAR`.
2. W2 inv `invoice_number "INV-9"`, `invoice_date MID`.
3. W2 proj `name "Far"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `result == []`.

### CAL-GE-16 — a database error reaches the caller unchanged
- **Rules:** `get_events` Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. `E = RuntimeError("db down")`.

**When**
- `svc.get_events(db, workspace_id=W1.id, start=START, end=END)`, inside **failing query**.

**Then**
1. raises: `exc.value is E`.

### CAL-GE-17 — maintenance logs on both edges appear under maintenance; the days outside do not
- **Rules:** `get_events` R6 [BUG-1805]
- **Kind:** bug
- **Expect:** xfail BUG-1805
- **Fails today on:** Then 1 (no maintenance collector: the list is empty)

**Given**
1. A1 = log `maintenance_date PRE`.
2. A2 = log `maintenance_date START`.
3. A3 = log `maintenance_date END`.
4. A4 = log `maintenance_date POST`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.maintenance])`.

**Then**
1. returns: `keys(result) == [(A2.id, "Maintenance date"), (A3.id, "Maintenance date")]`.
2. returns: `all(e.category == CC.maintenance for e in result)`, `all(e.source_type == "machine_maintenance_log" for e in result)`.
3. returns: `a2 = [e for e in result if e.record_id == A2.id][0]`; `a2.id == f"machine_maintenance_log:{A2.id}:maintenance_date"`, `a2.date == START`.
4. returns: `a3 = [e for e in result if e.record_id == A3.id][0]`; `a3.id == f"machine_maintenance_log:{A3.id}:maintenance_date"`, `a3.date == END`.

### CAL-GE-18 — a soft-deleted log gives no event; a live one does (no filter)
- **Rules:** `get_events` R6 [BUG-1805]
- **Kind:** bug
- **Expect:** xfail BUG-1805
- **Fails today on:** Then 1 (no maintenance event at all)

**Given**
1. G = log `maintenance_date MID`, but gone.
2. A = log `maintenance_date MID`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `recs(of("machine_maintenance_log")) == [A.id]`.

### CAL-GE-19 — logs of a deleted machine and of a deleted factory's machine still appear
- **Rules:** `get_events` R6 [BUG-1805]
- **Kind:** bug
- **Expect:** xfail BUG-1805
- **Fails today on:** Then 1 (no maintenance event at all)

**Given**
1. A1 = log `maintenance_date MID`, but `machine_id MD.id`.
2. A2 = log `maintenance_date MID`, but `machine_id MF.id`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.maintenance])`.

**Then**
1. returns: `recs(result) == sorted([A1.id, A2.id])`.

### CAL-GE-20 — the other workspace's logs (W0 and W2), before and after, never appear
- **Rules:** `get_events` R6 [BUG-1805]
- **Kind:** bug
- **Expect:** xfail BUG-1805
- **Fails today on:** Then 1 (no maintenance event at all)

**Given**
1. B9 = W2 log `maintenance_date MID`.
2. A = log `maintenance_date MID`.
3. C9 = W2 log `maintenance_date MID`.
4. Z0 = W0 log `maintenance_date MID`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.maintenance])`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-GE-21 — a log of this workspace linked to another workspace's machine gives no event
- **Rules:** `get_events` R6 [BUG-1805] (BUG-1101 shape)
- **Kind:** bug
- **Expect:** xfail BUG-1805
- **Fails today on:** Then 1 (no maintenance event at all)

**Given**
1. A = log `maintenance_date MID`.
2. X = log `maintenance_date MID`, but `machine_id M9.id`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.maintenance])`.

**Then**
1. returns: `recs(result) == [A.id]`.

## `CalendarService._collect_work_orders`

### CAL-WO-01 — a work order's two dates give two events with every field
- **Rules:** `_collect_work_orders` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = wo `work_order_number "WO-100"`, `planned_date MID`, `end_date date(2026, 5, 20)`, but `status WorkOrderStatusEnum.IN_PROGRESS.value`, `priority WorkOrderPriorityEnum.MEDIUM`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `result[0].id == f"work_order:{O.id}:planned_date"`, `result[0].category == CC.work_orders`, `result[0].source_type == "work_order"`, `result[0].record_id == O.id`.
3. returns: `result[0].date == MID`, `result[0].date_label == "Planned date"`.
4. returns: `result[0].title == "WO-100"`, `result[0].subtitle == "Fix press"`, `result[0].link == "/orders/work"`.
5. returns: `result[0].meta == {"status": "IN_PROGRESS", "priority": "MEDIUM"}`.
6. returns: `result[1].id == f"work_order:{O.id}:end_date"`, `result[1].date == date(2026, 5, 20)`, `result[1].date_label == "End date"`.

### CAL-WO-02 — planned_date: both edges in, the days outside out
- **Rules:** `_collect_work_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = wo `work_order_number "WO-1"`, `planned_date PRE`.
2. A2 = wo `work_order_number "WO-2"`, `planned_date START`.
3. A3 = wo `work_order_number "WO-3"`, `planned_date END`.
4. A4 = wo `work_order_number "WO-4"`, `planned_date POST`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Planned date"), (A3.id, "Planned date")]`.

### CAL-WO-03 — end_date: both edges in, the days outside out
- **Rules:** `_collect_work_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = wo `work_order_number "WO-1"`, `end_date PRE`.
2. A2 = wo `work_order_number "WO-2"`, `end_date START`.
3. A3 = wo `work_order_number "WO-3"`, `end_date END`.
4. A4 = wo `work_order_number "WO-4"`, `end_date POST`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "End date"), (A3.id, "End date")]`.

### CAL-WO-04 — one date in and one out gives only the event in range
- **Rules:** `_collect_work_orders` R1, R2; `_expand_date_fields` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = wo `work_order_number "WO-1"`, `planned_date PRE`, `end_date MID`.
2. A2 = wo `work_order_number "WO-2"`, `planned_date MID`, `end_date POST`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A1.id, "End date"), (A2.id, "Planned date")]`.

### CAL-WO-05 — the other workspace's orders (W0 and W2), before and after, never appear
- **Rules:** `_collect_work_orders` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 wo `work_order_number "WO-91"`, `planned_date MID`.
2. A = wo `work_order_number "WO-1"`, `planned_date MID`.
3. C9 = W2 wo `work_order_number "WO-92"`, `planned_date MID`.
4. Z0 = W0 wo `work_order_number "WO-90"`, `planned_date MID`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, {CC.work_orders, CC.purchase})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-WO-06 — a soft-deleted work order never appears
- **Rules:** `_collect_work_orders` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = wo `work_order_number "WO-9"`, `planned_date MID`, but deleted.
2. A = wo `work_order_number "WO-1"`, `planned_date MID`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-WO-07 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_work_orders` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = wo `work_order_number "WO-1"`, `planned_date MID`.
2. recorder.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, {CC.purchase})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

### CAL-OQ14-01 — a VOIDED work order gives no event (OQ-14 answered)
- **Rules:** `_collect_work_orders` R3 [BUG-1876]
- **Kind:** bug
- **Expect:** xfail BUG-1876
- **Fails today on:** Then 1 (V is listed with `meta.status "VOIDED"`)

**Given**
1. V = wo `work_order_number "WO-V"`, `planned_date MID`, but `status WorkOrderStatusEnum.VOIDED.value`, `void_note "Void"`, `voided_at T0`, `voided_by U1.id`.
2. A = wo `work_order_number "WO-A"`, `planned_date MID`, but `status WorkOrderStatusEnum.DRAFT.value`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-OQ14-02 — draft, in-progress and completed work orders are listed (OQ-14 answered)
- **Rules:** `_collect_work_orders` R3a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = wo `work_order_number "WO-D"`, `planned_date MID`, but `status WorkOrderStatusEnum.DRAFT.value`.
2. A2 = wo `work_order_number "WO-C"`, `planned_date MID`, but `status WorkOrderStatusEnum.COMPLETED.value`, `completed_at T0`.
3. A3 = wo `work_order_number "WO-P"`, `planned_date MID`, but `status WorkOrderStatusEnum.IN_PROGRESS.value`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id, A3.id]`.

### CAL-OQ15-01 — a work order of a soft-deleted factory gives no event (OQ-15 answered)
- **Rules:** `_collect_work_orders` R4 [BUG-1877]
- **Kind:** bug
- **Expect:** xfail BUG-1877
- **Fails today on:** Then 1 (X is listed)

**Given**
1. X = wo `work_order_number "WO-F"`, `planned_date MID`, but `factory_id FD.id`.
2. A = wo `work_order_number "WO-A"`, `planned_date MID`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-WO-08 — a work order of an inactive but live factory still appears
- **Rules:** `_collect_work_orders` R4 (part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = wo `work_order_number "WO-I"`, `planned_date MID`, but `factory_id FI.id`.
2. A2 = wo `work_order_number "WO-A"`, `planned_date MID`.

**When**
- `result = svc._collect_work_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id]`.

## `CalendarService._collect_purchase_orders`

### CAL-PO-01 — a purchase order's three dates give three events with every field
- **Rules:** `_collect_purchase_orders` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = po `po_number "PO-100"`, `order_date MID`, `expected_delivery_date date(2026, 5, 15)`, `actual_delivery_date date(2026, 5, 20)`, but `account_id AC1.id`.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `[e.date_label for e in result] == ["Order date", "Expected delivery", "Actual delivery"]`.
2. returns: `[e.date for e in result] == [MID, date(2026, 5, 15), date(2026, 5, 20)]`.
3. returns: `[e.id for e in result] == [f"purchase_order:{O.id}:order_date", f"purchase_order:{O.id}:expected_delivery_date", f"purchase_order:{O.id}:actual_delivery_date"]`.
4. returns: `result[0].category == CC.purchase`, `result[0].source_type == "purchase_order"`, `result[0].record_id == O.id`.
5. returns: `result[0].title == "PO-100"`, `result[0].subtitle == "Steel order"`, `result[0].link == f"/orders/purchase?orderId={O.id}"`.
6. returns: `result[0].meta == {"total_amount": "10.50", "account_id": AC1.id, "current_status_id": S1.id}`.

### CAL-PO-02 — no account: meta account_id is None
- **Rules:** `_collect_purchase_orders` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = po `po_number "PO-101"`, `order_date MID`.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].meta["account_id"] is None`.

### CAL-PO-03 — order_date: both edges in, the days outside out
- **Rules:** `_collect_purchase_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = po `po_number "PO-1"`, `order_date PRE`.
2. A2 = po `po_number "PO-2"`, `order_date START`.
3. A3 = po `po_number "PO-3"`, `order_date END`.
4. A4 = po `po_number "PO-4"`, `order_date POST`.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Order date"), (A3.id, "Order date")]`.

### CAL-PO-04 — expected_delivery_date: both edges in, the days outside out
- **Rules:** `_collect_purchase_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = po `po_number "PO-1"`, `expected_delivery_date PRE`.
2. A2 = po `po_number "PO-2"`, `expected_delivery_date START`.
3. A3 = po `po_number "PO-3"`, `expected_delivery_date END`.
4. A4 = po `po_number "PO-4"`, `expected_delivery_date POST`.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Expected delivery"), (A3.id, "Expected delivery")]`.

### CAL-PO-05 — actual_delivery_date: both edges in, the days outside out
- **Rules:** `_collect_purchase_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = po `po_number "PO-1"`, `actual_delivery_date PRE`.
2. A2 = po `po_number "PO-2"`, `actual_delivery_date START`.
3. A3 = po `po_number "PO-3"`, `actual_delivery_date END`.
4. A4 = po `po_number "PO-4"`, `actual_delivery_date POST`.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Actual delivery"), (A3.id, "Actual delivery")]`.

### CAL-PO-06 — a voided purchase order never appears; a live draft one does
- **Rules:** `_collect_purchase_orders` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. V = po `po_number "PO-9"`, `order_date MID`, but voided.
2. A = po `po_number "PO-1"`, `order_date MID`.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PO-07 — the other workspace's orders (W0 and W2), before and after, never appear
- **Rules:** `_collect_purchase_orders` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 po `po_number "PO-91"`, `order_date MID`.
2. A = po `po_number "PO-1"`, `order_date MID`.
3. C9 = W2 po `po_number "PO-92"`, `order_date MID`.
4. Z0 = W0 po `po_number "PO-90"`, `order_date MID`, but `destination_id F0.id`.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, {CC.purchase, CC.expense})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PO-08 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_purchase_orders` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = po `po_number "PO-1"`, `order_date MID`.
2. recorder.

**When**
- `result = svc._collect_purchase_orders(db, W1.id, START, END, {CC.expense})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

## `CalendarService._collect_expense_orders`

### CAL-EO-01 — an expense order's two dates give two events with every field
- **Rules:** `_collect_expense_orders` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = eo `expense_number "EXP-100"`, `expense_date MID`, `due_date date(2026, 5, 25)`.

**When**
- `result = svc._collect_expense_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `[e.date_label for e in result] == ["Expense date", "Due date"]`.
2. returns: `[e.date for e in result] == [MID, date(2026, 5, 25)]`.
3. returns: `[e.id for e in result] == [f"expense_order:{O.id}:expense_date", f"expense_order:{O.id}:due_date"]`.
4. returns: `result[0].category == CC.expense`, `result[0].source_type == "expense_order"`, `result[0].record_id == O.id`.
5. returns: `result[0].title == "EXP-100"`, `result[0].subtitle == "Power bill"`, `result[0].link == "/orders/expense"`.
6. returns: `result[0].meta == {"category": "other", "total_amount": "20.00"}`.

### CAL-EO-02 — expense_date: both edges in, the days outside out
- **Rules:** `_collect_expense_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = eo `expense_number "EXP-1"`, `expense_date PRE`.
2. A2 = eo `expense_number "EXP-2"`, `expense_date START`.
3. A3 = eo `expense_number "EXP-3"`, `expense_date END`.
4. A4 = eo `expense_number "EXP-4"`, `expense_date POST`.

**When**
- `result = svc._collect_expense_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Expense date"), (A3.id, "Expense date")]`.

### CAL-EO-03 — due_date: both edges in, the days outside out
- **Rules:** `_collect_expense_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = eo `expense_number "EXP-1"`, `expense_date FAR`, `due_date PRE`.
2. A2 = eo `expense_number "EXP-2"`, `expense_date FAR`, `due_date START`.
3. A3 = eo `expense_number "EXP-3"`, `expense_date FAR`, `due_date END`.
4. A4 = eo `expense_number "EXP-4"`, `expense_date FAR`, `due_date POST`.

**When**
- `result = svc._collect_expense_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Due date"), (A3.id, "Due date")]`.

### CAL-EO-04 — a voided expense order never appears
- **Rules:** `_collect_expense_orders` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. V = eo `expense_number "EXP-9"`, `expense_date MID`, but voided.
2. A = eo `expense_number "EXP-1"`, `expense_date MID`.

**When**
- `result = svc._collect_expense_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-EO-05 — the other workspace's orders (W0 and W2), before and after, never appear
- **Rules:** `_collect_expense_orders` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 eo `expense_number "EXP-91"`, `expense_date MID`.
2. A = eo `expense_number "EXP-1"`, `expense_date MID`.
3. C9 = W2 eo `expense_number "EXP-92"`, `expense_date MID`.
4. Z0 = W0 eo `expense_number "EXP-90"`, `expense_date MID`.

**When**
- `result = svc._collect_expense_orders(db, W1.id, START, END, {CC.expense, CC.purchase})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-EO-06 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_expense_orders` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = eo `expense_number "EXP-1"`, `expense_date MID`.
2. recorder.

**When**
- `result = svc._collect_expense_orders(db, W1.id, START, END, {CC.purchase})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

## `CalendarService._collect_sales_orders`

### CAL-SO-01 — a sales order's two dates give two events with every field
- **Rules:** `_collect_sales_orders` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = so `sales_order_number "SO-100"`, `order_date MID`, `expected_delivery_date date(2026, 5, 22)`.

**When**
- `result = svc._collect_sales_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `[e.date_label for e in result] == ["Order date", "Expected delivery"]`.
2. returns: `[e.date for e in result] == [MID, date(2026, 5, 22)]`.
3. returns: `[e.id for e in result] == [f"sales_order:{O.id}:order_date", f"sales_order:{O.id}:expected_delivery_date"]`.
4. returns: `result[0].category == CC.sales`, `result[0].source_type == "sales_order"`, `result[0].record_id == O.id`.
5. returns: `result[0].title == "SO-100"`, `result[0].subtitle == "Chairs"`, `result[0].link == "/sales/overview"`.
6. returns: `result[0].meta == {"total_amount": "30.00"}`.

### CAL-SO-02 — order_date: both edges in, the days outside out
- **Rules:** `_collect_sales_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = so `sales_order_number "SO-1"`, `order_date PRE`.
2. A2 = so `sales_order_number "SO-2"`, `order_date START`.
3. A3 = so `sales_order_number "SO-3"`, `order_date END`.
4. A4 = so `sales_order_number "SO-4"`, `order_date POST`.

**When**
- `result = svc._collect_sales_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Order date"), (A3.id, "Order date")]`.

### CAL-SO-03 — expected_delivery_date: both edges in, the days outside out
- **Rules:** `_collect_sales_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = so `sales_order_number "SO-1"`, `order_date FAR`, `expected_delivery_date PRE`.
2. A2 = so `sales_order_number "SO-2"`, `order_date FAR`, `expected_delivery_date START`.
3. A3 = so `sales_order_number "SO-3"`, `order_date FAR`, `expected_delivery_date END`.
4. A4 = so `sales_order_number "SO-4"`, `order_date FAR`, `expected_delivery_date POST`.

**When**
- `result = svc._collect_sales_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Expected delivery"), (A3.id, "Expected delivery")]`.

### CAL-SO-04 — the other workspace's orders (W0 and W2), before and after, never appear
- **Rules:** `_collect_sales_orders` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 so `sales_order_number "SO-91"`, `order_date MID`.
2. A = so `sales_order_number "SO-1"`, `order_date MID`.
3. C9 = W2 so `sales_order_number "SO-92"`, `order_date MID`.
4. Z0 = W0 so `sales_order_number "SO-90"`, `order_date MID`.

**When**
- `result = svc._collect_sales_orders(db, W1.id, START, END, {CC.sales, CC.invoices})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-SO-05 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_sales_orders` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = so `sales_order_number "SO-1"`, `order_date MID`.
2. recorder.

**When**
- `result = svc._collect_sales_orders(db, W1.id, START, END, {CC.invoices})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

### CAL-OQ15-02 — a sales order of a soft-deleted factory gives no event (OQ-15 answered)
- **Rules:** `_collect_sales_orders` R3 [BUG-1878]
- **Kind:** bug
- **Expect:** xfail BUG-1878
- **Fails today on:** Then 1 (X is listed)

**Given**
1. X = so `sales_order_number "SO-F"`, `order_date MID`, but `factory_id FD.id`.
2. A = so `sales_order_number "SO-A"`, `order_date MID`.

**When**
- `result = svc._collect_sales_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-SO-06 — a sales order of an inactive but live factory still appears
- **Rules:** `_collect_sales_orders` R3 (part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = so `sales_order_number "SO-I"`, `order_date MID`, but `factory_id FI.id`.
2. A2 = so `sales_order_number "SO-A"`, `order_date MID`.

**When**
- `result = svc._collect_sales_orders(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id]`.

## `CalendarService._collect_sales_deliveries`

### CAL-SD-01 — a delivery's two dates give two events with every field
- **Rules:** `_collect_sales_deliveries` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. D = dl `delivery_number "SD-100"`, `scheduled_date MID`, `actual_delivery_date date(2026, 5, 12)`, but `delivery_status "delivered"`.

**When**
- `result = svc._collect_sales_deliveries(db, W1.id, START, END, None)`.

**Then**
1. returns: `[e.date_label for e in result] == ["Scheduled delivery", "Actual delivery"]`.
2. returns: `[e.date for e in result] == [MID, date(2026, 5, 12)]`.
3. returns: `[e.id for e in result] == [f"sales_delivery:{D.id}:scheduled_date", f"sales_delivery:{D.id}:actual_delivery_date"]`.
4. returns: `result[0].category == CC.sales`, `result[0].source_type == "sales_delivery"`, `result[0].record_id == D.id`.
5. returns: `result[0].title == "SD-100"`, `result[0].subtitle == f"Sales order #{SOX.id}"`, `result[0].link == "/sales/pipeline"`.
6. returns: `result[0].meta == {"delivery_status": "delivered"}`.

### CAL-SD-02 — scheduled_date: both edges in, the days outside out
- **Rules:** `_collect_sales_deliveries` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = dl `delivery_number "SD-1"`, `scheduled_date PRE`.
2. A2 = dl `delivery_number "SD-2"`, `scheduled_date START`.
3. A3 = dl `delivery_number "SD-3"`, `scheduled_date END`.
4. A4 = dl `delivery_number "SD-4"`, `scheduled_date POST`.

**When**
- `result = svc._collect_sales_deliveries(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Scheduled delivery"), (A3.id, "Scheduled delivery")]`.

### CAL-SD-03 — actual_delivery_date: both edges in, the days outside out
- **Rules:** `_collect_sales_deliveries` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = dl `delivery_number "SD-1"`, `actual_delivery_date PRE`.
2. A2 = dl `delivery_number "SD-2"`, `actual_delivery_date START`.
3. A3 = dl `delivery_number "SD-3"`, `actual_delivery_date END`.
4. A4 = dl `delivery_number "SD-4"`, `actual_delivery_date POST`.

**When**
- `result = svc._collect_sales_deliveries(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Actual delivery"), (A3.id, "Actual delivery")]`.

### CAL-SD-04 — a cancelled delivery never appears; planned and delivered ones do
- **Rules:** `_collect_sales_deliveries` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = dl `delivery_number "SD-9"`, `scheduled_date MID`, but `delivery_status "cancelled"`.
2. A1 = dl `delivery_number "SD-1"`, `scheduled_date MID`.
3. A2 = dl `delivery_number "SD-2"`, `scheduled_date MID`, but `delivery_status "delivered"`.

**When**
- `result = svc._collect_sales_deliveries(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id]`.

### CAL-SD-05 — the other workspace's deliveries (W0 and W2), before and after, never appear
- **Rules:** `_collect_sales_deliveries` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 dl `delivery_number "SD-91"`, `scheduled_date MID`.
2. A = dl `delivery_number "SD-1"`, `scheduled_date MID`.
3. C9 = W2 dl `delivery_number "SD-92"`, `scheduled_date MID`.
4. Z0 = W0 dl `delivery_number "SD-90"`, `scheduled_date MID`.

**When**
- `result = svc._collect_sales_deliveries(db, W1.id, START, END, {CC.sales})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-SD-06 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_sales_deliveries` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = dl `delivery_number "SD-1"`, `scheduled_date MID`.
2. recorder.

**When**
- `result = svc._collect_sales_deliveries(db, W1.id, START, END, {CC.invoices})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

### CAL-SD-07 — "Cancelled" is not exactly "cancelled": that delivery is listed
- **Rules:** `_collect_sales_deliveries` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = dl `delivery_number "SD-9"`, `scheduled_date MID`, but `delivery_status "cancelled"`.
2. A = dl `delivery_number "SD-1"`, `scheduled_date MID`, but `delivery_status "Cancelled"`.

**When**
- `result = svc._collect_sales_deliveries(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

## `CalendarService._collect_invoices`

### CAL-IN-01 — an invoice's two dates give two events with every field
- **Rules:** `_collect_invoices` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. I = inv `invoice_number "INV-100"`, `invoice_date MID`, `due_date date(2026, 5, 28)`.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, None)`.

**Then**
1. returns: `[e.date_label for e in result] == ["Invoice date", "Due date"]`.
2. returns: `[e.date for e in result] == [MID, date(2026, 5, 28)]`.
3. returns: `[e.id for e in result] == [f"account_invoice:{I.id}:invoice_date", f"account_invoice:{I.id}:due_date"]`.
4. returns: `result[0].category == CC.invoices`, `result[0].source_type == "account_invoice"`, `result[0].record_id == I.id`.
5. returns: `result[0].title == "INV-100"`, `result[0].subtitle == "May rent"`, `result[0].link == f"/accounts/{AC1.id}?invoiceId={I.id}"`.
6. returns: `result[0].meta == {"account_id": AC1.id, "invoice_type": "payable", "payment_status": "unpaid", "invoice_amount": "100.00"}`.

### CAL-IN-02 — invoice_date: both edges in, the days outside out
- **Rules:** `_collect_invoices` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = inv `invoice_number "INV-1"`, `invoice_date PRE`.
2. A2 = inv `invoice_number "INV-2"`, `invoice_date START`.
3. A3 = inv `invoice_number "INV-3"`, `invoice_date END`.
4. A4 = inv `invoice_number "INV-4"`, `invoice_date POST`.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Invoice date"), (A3.id, "Invoice date")]`.

### CAL-IN-03 — due_date: both edges in, the days outside out
- **Rules:** `_collect_invoices` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = inv `invoice_number "INV-1"`, `invoice_date FAR`, `due_date PRE`.
2. A2 = inv `invoice_number "INV-2"`, `invoice_date FAR`, `due_date START`.
3. A3 = inv `invoice_number "INV-3"`, `invoice_date FAR`, `due_date END`.
4. A4 = inv `invoice_number "INV-4"`, `invoice_date FAR`, `due_date POST`.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Due date"), (A3.id, "Due date")]`.

### CAL-IN-04 — a voided invoice never appears; draft and confirmed ones do
- **Rules:** `_collect_invoices` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. V = inv `invoice_number "INV-9"`, `invoice_date MID`, but voided.
2. A1 = inv `invoice_number "INV-1"`, `invoice_date MID`, but `invoice_status "draft"`.
3. A2 = inv `invoice_number "INV-2"`, `invoice_date MID`.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id]`.

### CAL-IN-05 — the other workspace's invoices (W0 and W2), before and after, never appear
- **Rules:** `_collect_invoices` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 inv `invoice_number "INV-91"`, `invoice_date MID`.
2. A = inv `invoice_number "INV-1"`, `invoice_date MID`.
3. C9 = W2 inv `invoice_number "INV-92"`, `invoice_date MID`.
4. Z0 = W0 inv `invoice_number "INV-90"`, `invoice_date MID`.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, {CC.invoices, CC.sales})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-IN-06 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_invoices` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = inv `invoice_number "INV-1"`, `invoice_date MID`.
2. recorder.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, {CC.sales})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

### CAL-IN-07 — an empty invoice number is titled Invoice #<id>
- **Rules:** `_collect_invoices` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = inv `invoice_number ""`, `invoice_date MID`.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].title == f"Invoice #{I.id}"`.

### CAL-IN-08 — no invoice number is titled Invoice #<id>
- **Rules:** `_collect_invoices` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = inv `invoice_number None`, `invoice_date MID`.

**When**
- `result = svc._collect_invoices(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].title == f"Invoice #{I.id}"`.

## `CalendarService._collect_invoice_payments`

### CAL-PY-01 — a payment gives one event with every field, ids taken from its invoice
- **Rules:** `_collect_invoice_payments` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Y = pay `payment_date MID`.

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id == f"invoice_payment:{Y.id}:payment_date"`, `result[0].category == CC.invoices`, `result[0].source_type == "invoice_payment"`, `result[0].record_id == Y.id`.
3. returns: `result[0].date == MID`, `result[0].date_label == "Payment date"`.
4. returns: `result[0].title == f"Payment #{Y.id}"`, `result[0].subtitle == f"Invoice #{INX.id}"`.
5. returns: `result[0].link == f"/accounts/{AC1.id}?invoiceId={INX.id}"`.
6. returns: `result[0].meta == {"invoice_id": INX.id, "account_id": AC1.id, "payment_amount": "40.00", "payment_method": "cash"}`.

### CAL-PY-02 — no payment method: meta payment_method is None
- **Rules:** `_collect_invoice_payments` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Y = pay `payment_date MID`, but `payment_method None`.

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].meta["payment_method"] is None`.

### CAL-PY-03 — payment_date: both edges in, the days outside out
- **Rules:** `_collect_invoice_payments` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = pay `payment_date PRE`.
2. A2 = pay `payment_date START`.
3. A3 = pay `payment_date END`.
4. A4 = pay `payment_date POST`.

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Payment date"), (A3.id, "Payment date")]`.

### CAL-PY-04 — a voided payment never appears
- **Rules:** `_collect_invoice_payments` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. V = pay `payment_date MID`, but voided.
2. A = pay `payment_date MID`.

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PY-05 — the invoice's own status is not looked at
- **Rules:** `_collect_invoice_payments` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VI = inv `invoice_number "INV-V"`, `invoice_date FAR`, but voided.
2. Y = pay `payment_date MID`, but `invoice_id VI.id`.

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [Y.id]`.
2. returns: `result[0].meta["invoice_id"] == VI.id`.

### CAL-PY-06 — the other workspace's payments (W0 and W2), before and after, never appear
- **Rules:** `_collect_invoice_payments` R1 (the payment's own workspace decides); `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 pay `payment_date MID`.
2. A = pay `payment_date MID`.
3. C9 = W2 pay `payment_date MID`.
4. Z0 = W0 pay `payment_date MID`.
5. X2 = W2 pay `payment_date MID`, but `invoice_id INX.id` (a W2 payment linked to W1's invoice).

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, {CC.invoices})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PY-07 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_invoice_payments` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = pay `payment_date MID`.
2. recorder.

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, {CC.sales})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

### CAL-PY-08 — a payment linked to another workspace's invoice gives no event
- **Rules:** `_collect_invoice_payments` R3 [BUG-1801]
- **Kind:** bug
- **Expect:** xfail BUG-1801
- **Fails today on:** Then 1 (X is listed with W2's invoice id and account id)

**Given**
1. A = pay `payment_date MID`.
2. X = pay `payment_date MID`, but `invoice_id INX9.id`.

**When**
- `result = svc._collect_invoice_payments(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.
2. returns: `all(e.meta["invoice_id"] != INX9.id for e in result)`.
3. returns: `all(e.meta["account_id"] != AC9.id for e in result)`.

## `CalendarService._collect_production_batches`

### CAL-PB-01 — a batch gives one event with every field
- **Rules:** `_collect_production_batches` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = batch `batch_number "BATCH-2026-014"`, `batch_date MID`, but `status "in_progress"`.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id == f"production_batch:{B.id}:batch_date"`, `result[0].category == CC.production`, `result[0].source_type == "production_batch"`, `result[0].record_id == B.id`.
3. returns: `result[0].date == MID`, `result[0].date_label == "Batch date"`.
4. returns: `result[0].title == "BATCH-2026-014"`, `result[0].subtitle == "Run A"`, `result[0].link == "/production"`.
5. returns: `result[0].meta == {"status": "in_progress"}`.

### CAL-PB-02 — batch_date: both edges in, the days outside out
- **Rules:** `_collect_production_batches` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = batch `batch_number "B-1"`, `batch_date PRE`.
2. A2 = batch `batch_number "B-2"`, `batch_date START`.
3. A3 = batch `batch_number "B-3"`, `batch_date END`.
4. A4 = batch `batch_number "B-4"`, `batch_date POST`.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Batch date"), (A3.id, "Batch date")]`.

### CAL-PB-03 — a cancelled batch never appears; draft and in-progress ones do
- **Rules:** `_collect_production_batches` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = batch `batch_number "B-9"`, `batch_date MID`, but cancelled.
2. A1 = batch `batch_number "B-1"`, `batch_date MID`.
3. A2 = batch `batch_number "B-2"`, `batch_date MID`, but `status "in_progress"`.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id]`.

### CAL-PB-04 — batches of an inactive line and of an inactive factory's line still appear
- **Rules:** `_collect_production_batches` R2 (part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = batch `batch_number "B-1"`, `batch_date MID`, but `production_line_id LI.id`.
2. A2 = batch `batch_number "B-2"`, `batch_date MID`, but `production_line_id LFI.id`.
3. A3 = batch `batch_number "B-3"`, `batch_date MID`.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id, A3.id]`.

### CAL-PB-05 — the other workspace's batches (W0 and W2), before and after, never appear
- **Rules:** `_collect_production_batches` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 batch `batch_number "B-91"`, `batch_date MID`.
2. A = batch `batch_number "B-1"`, `batch_date MID`.
3. C9 = W2 batch `batch_number "B-92"`, `batch_date MID`.
4. Z0 = W0 batch `batch_number "B-90"`, `batch_date MID`.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, {CC.production})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PB-06 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_production_batches` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = batch `batch_number "B-1"`, `batch_date MID`.
2. recorder.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, {CC.projects})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

### CAL-PB-07 — a batch whose line's factory is soft-deleted gives no event
- **Rules:** `_collect_production_batches` R2 [BUG-1807]
- **Kind:** bug
- **Expect:** xfail BUG-1807
- **Fails today on:** Then 1 (X is listed)

**Given**
1. X = batch `batch_number "B-9"`, `batch_date MID`, but `production_line_id LD.id`.
2. A = batch `batch_number "B-1"`, `batch_date MID`.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PB-08 — "Cancelled" is not exactly "cancelled": that batch is listed
- **Rules:** `_collect_production_batches` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = batch `batch_number "B-9"`, `batch_date MID`, but cancelled.
2. A = batch `batch_number "B-1"`, `batch_date MID`, but `status "Cancelled"`.

**When**
- `result = svc._collect_production_batches(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

## `CalendarService._collect_projects`

### CAL-PJ-01 — a project's three dates give three events with every field
- **Rules:** `_collect_projects` R1, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Line 3 refit"`, `start_date datetime(2026, 5, 2, 8, 0)`, `end_date datetime(2026, 5, 20, 17, 0)`, `deadline datetime(2026, 5, 25, 12, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `[e.date_label for e in result] == ["Start date", "End date", "Deadline"]`.
2. returns: `[e.date for e in result] == [date(2026, 5, 2), date(2026, 5, 20), date(2026, 5, 25)]`.
3. returns: `[e.id for e in result] == [f"project:{P.id}:start_date", f"project:{P.id}:end_date", f"project:{P.id}:deadline"]`.
4. returns: `result[0].category == CC.projects`, `result[0].source_type == "project"`, `result[0].record_id == P.id`.
5. returns: `result[0].title == "Line 3 refit"`, `result[0].subtitle == "Main"`, `result[0].link == "/project"`.
6. returns: `result[0].meta == {"status": "PLANNING"}`.

### CAL-PJ-02 — start_date: any time on an edge day is in, the instants outside are out
- **Rules:** `_collect_projects` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = proj `name "P1"`, `start_date datetime(2026, 4, 30, 23, 59, 59, 999999)`.
2. A2 = proj `name "P2"`, `start_date datetime(2026, 5, 1, 0, 0)`.
3. A3 = proj `name "P3"`, `start_date datetime(2026, 5, 31, 23, 30)`.
4. A4 = proj `name "P4"`, `start_date datetime(2026, 5, 31, 23, 59, 59, 999999)`.
5. A5 = proj `name "P5"`, `start_date datetime(2026, 6, 1, 0, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Start date"), (A3.id, "Start date"), (A4.id, "Start date")]`.
2. returns: `{e.record_id: e.date for e in result} == {A2.id: START, A3.id: END, A4.id: END}`.

### CAL-PJ-03 — end_date: any time on an edge day is in, the instants outside are out
- **Rules:** `_collect_projects` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = proj `name "P1"`, `end_date datetime(2026, 4, 30, 23, 59, 59, 999999)`.
2. A2 = proj `name "P2"`, `end_date datetime(2026, 5, 1, 0, 0)`.
3. A3 = proj `name "P3"`, `end_date datetime(2026, 5, 31, 23, 30)`.
4. A4 = proj `name "P4"`, `end_date datetime(2026, 5, 31, 23, 59, 59, 999999)`.
5. A5 = proj `name "P5"`, `end_date datetime(2026, 6, 1, 0, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "End date"), (A3.id, "End date"), (A4.id, "End date")]`.
2. returns: `{e.record_id: e.date for e in result} == {A2.id: START, A3.id: END, A4.id: END}`.

### CAL-PJ-04 — deadline: any time on an edge day is in, the instants outside are out
- **Rules:** `_collect_projects` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = proj `name "P1"`, `deadline datetime(2026, 4, 30, 23, 59, 59, 999999)`.
2. A2 = proj `name "P2"`, `deadline datetime(2026, 5, 1, 0, 0)`.
3. A3 = proj `name "P3"`, `deadline datetime(2026, 5, 31, 23, 30)`.
4. A4 = proj `name "P4"`, `deadline datetime(2026, 5, 31, 23, 59, 59, 999999)`.
5. A5 = proj `name "P5"`, `deadline datetime(2026, 6, 1, 0, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `keys(result) == [(A2.id, "Deadline"), (A3.id, "Deadline"), (A4.id, "Deadline")]`.
2. returns: `{e.record_id: e.date for e in result} == {A2.id: START, A3.id: END, A4.id: END}`.

### CAL-PJ-05 — subtitle: 120 characters kept whole, 121 cut to 120
- **Rules:** `_collect_projects` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `description "x" * 120`.
2. A2 = proj `name "P2"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `description "x" * 120 + "Y"`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `{e.record_id: e.subtitle for e in result} == {A1.id: "x" * 120, A2.id: "x" * 120}`.

### CAL-PJ-06 — an empty description gives no subtitle
- **Rules:** `_collect_projects` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `description ""`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].subtitle is None`.

### CAL-PJ-07 — the other workspace's projects (W0 and W2), before and after, never appear
- **Rules:** `_collect_projects` R1; `_category_allowed` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B9 = W2 proj `name "Far 1"`, `start_date datetime(2026, 5, 10, 9, 0)`.
2. A = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`.
3. C9 = W2 proj `name "Far 2"`, `start_date datetime(2026, 5, 10, 9, 0)`.
4. Z0 = W0 proj `name "Zero 1"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, {CC.projects, CC.production})`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PJ-08 — another category allowed: [] and no SQL sent
- **Rules:** `_collect_projects` R1; `_category_allowed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`.
2. recorder.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, {CC.production})`.

**Then**
1. returns: `result == []`.
2. statement: `stmts == []`.

### CAL-PJ-09 — a project of an inactive but live factory still appears
- **Rules:** `_collect_projects` R3 (part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `factory_id FI.id`.
2. A2 = proj `name "P2"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id]`.

### CAL-PJ-10 — a soft-deleted project gives no event
- **Rules:** `_collect_projects` R2 [BUG-1800]
- **Kind:** bug
- **Expect:** xfail BUG-1800
- **Fails today on:** Then 1 (D is listed)

**Given**
1. D = proj `name "Gone"`, `start_date datetime(2026, 5, 10, 9, 0)`, but deleted.
2. A = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PJ-11 — a project of a soft-deleted factory gives no event
- **Rules:** `_collect_projects` R3 [BUG-1806]
- **Kind:** bug
- **Expect:** xfail BUG-1806
- **Fails today on:** Then 1 (X is listed)

**Given**
1. X = proj `name "Lost"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `factory_id FD.id`.
2. A = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A.id]`.

### CAL-PJ-12 — every project status is listed, meta.status is its value text
- **Rules:** `_collect_projects` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = proj `name "P1"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `status ProjectStatusEnum.IN_PROGRESS`.
2. A2 = proj `name "P2"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `status ProjectStatusEnum.COMPLETED`.
3. A3 = proj `name "P3"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `status ProjectStatusEnum.ON_HOLD`.
4. A4 = proj `name "P4"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `status ProjectStatusEnum.CANCELLED`.
5. A5 = proj `name "P5"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc._collect_projects(db, W1.id, START, END, None)`.

**Then**
1. returns: `recs(result) == [A1.id, A2.id, A3.id, A4.id, A5.id]`.
2. returns: `{e.record_id: e.meta["status"] for e in result} == {A1.id: "IN_PROGRESS", A2.id: "COMPLETED", A3.id: "ON_HOLD", A4.id: "CANCELLED", A5.id: "PLANNING"}`.

### CAL-OQ5-01 — a member who may not open a private project does not see it (refused caller)
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** isolation
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team").
2. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
3. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == [PW.id]`.

### CAL-OQ5-02 — the workspace owner sees a private project
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** happy
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team").
2. `W1.owner_user_id = UX.id`, then `db.flush()`.
3. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
4. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == sorted([PV.id, PW.id])`.

### CAL-OQ5-03 — an active member with role owner sees a private project
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** happy
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "owner").
2. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
3. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == sorted([PV.id, PW.id])`.

### CAL-OQ5-04 — an active ground-team-manager sees a private project
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** happy
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team-manager").
2. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
3. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == sorted([PV.id, PW.id])`.

### CAL-OQ5-05 — the project's creator sees a private project
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** happy
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team").
2. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by UX.id`.
3. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == sorted([PV.id, PW.id])`.

### CAL-OQ5-06 — a project member sees a private project
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** happy
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team").
2. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
3. project member(PV, UX).
4. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == sorted([PV.id, PW.id])`.

### CAL-OQ5-07 — an inactive ground-team-manager does not see a private project (refused caller)
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** isolation
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team-manager", status="inactive").
2. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
3. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == [PW.id]`.

### CAL-OQ5-08 — a private project with no creator is refused to a plain member (refused caller)
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** isolation
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team").
2. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)` (`created_by` not passed: NULL).
3. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == [PW.id]`.

### CAL-OQ5-09 — a member of another project only does not see this private project (refused caller)
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** isolation
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team").
2. PO = private proj `name "Other"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
3. project member(PO, UX).
4. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
5. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == sorted([PO.id, PW.id])`.

### CAL-OQ5-10 — the owner of another workspace only does not see this private project (refused caller)
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** isolation
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`; member(UX, "ground-team").
2. `W2.owner_user_id = UX.id`, then `db.flush()`.
3. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
4. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == [PW.id]`.

### CAL-OQ5-11 — a caller privileged only in other workspaces does not see this private project (refused caller)
- **Rules:** `_collect_projects` R6 [BUG-1869]; `get_events` R7
- **Kind:** isolation
- **Expect:** xfail BUG-1869
- **Fails today on:** Then 1 (the call raises TypeError: `get_events` has no `user_id` today)

**Given**
1. `UX = make_profile(db)`.
2. `WorkspaceMember(workspace_id=W2.id, user_id=UX.id, role="owner", status="active")`, flushed first (lowest membership id of UX).
3. `WorkspaceMember(workspace_id=W0.id, user_id=UX.id, role="ground-team-manager", status="active")`, flushed second.
4. member(UX, "ground-team") (the W1 row), flushed last, so its id is above both privileged rows.
5. PV = private proj `name "Secret"`, `start_date datetime(2026, 5, 10, 9, 0)`, but `created_by U1.id`.
6. PW = proj `name "Open"`, `start_date datetime(2026, 5, 10, 9, 0)`.

**When**
- `result = svc.get_events(db, workspace_id=W1.id, start=START, end=END, types=[CC.projects], user_id=UX.id)`.

**Then**
1. returns: `recs(result) == [PW.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Integration-only: `ValueError` → 400 | `GET /calendar/events` | `start > end` answers 400 with `start must be on or before end`; any other exception 500 `Internal server error` |
| Integration-only: query parsing, `total` | `GET /calendar/events` | `start`, `end`, repeated `types` parsed; `total == len(events)` |

## Spec gaps
None. Revision 1's gaps 1–5 are closed by the spec's Gap log G1–G5 (2026-11-04): private value `"invited_only"` (G1); amounts NOT NULL, amount text (G2); minimum rows (G3); project statuses (G4); what each close writes (G5).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_event_id` | R1 | CAL-ID-01, CAL-XF-01, CAL-PY-01, CAL-PB-01 |
| `_date_in_range` | R1 | CAL-DR-01 … DR-06, CAL-XF-04 |
| `_dt_to_date` | R1 | CAL-DT-01, CAL-DT-02, CAL-DT-03, CAL-PJ-02 … PJ-04 |
| `get_events` | R1; Errors row 1 | CAL-GE-01, CAL-GE-02 |
| `get_events` | R2 | CAL-GE-04 … GE-09 |
| `get_events` | R3 | CAL-GE-03, CAL-GE-04, CAL-GE-07, CAL-GE-08 |
| `get_events` | R4 | CAL-GE-10 … GE-13 |
| `get_events` | R5 (incl. TC6) | CAL-GE-03, CAL-GE-14, CAL-GE-15 |
| `get_events` | R6 [BUG-1805] | CAL-GE-17 … GE-21 |
| `get_events` | R7 [BUG-1869] | CAL-OQ5-01 … OQ5-11 |
| `get_events` | Errors row 2 | CAL-GE-16 |
| `_category_allowed` | R1 | CAL-CA-01 … CA-04; per collector: WO-05, WO-07, PO-07, PO-08, EO-05, EO-06, SO-04, SO-05, SD-05, SD-06, IN-05, IN-06, PY-06, PY-07, PB-05, PB-06, PJ-07, PJ-08 |
| `_expand_date_fields` | R1 | CAL-XF-01, CAL-XF-02, CAL-XF-03 |
| `_expand_date_fields` | R2 | CAL-XF-02, CAL-XF-04, CAL-WO-04 |
| `_expand_date_fields` | R3 | CAL-XF-01, CAL-XF-05 |
| `_expand_date_fields` | R4 | CAL-XF-06, CAL-GE-11 |
| `_expand_date_fields` | Errors (non-string title) | CAL-XF-07 |
| `_collect_work_orders` | R1 | CAL-WO-02 … WO-07 |
| `_collect_work_orders` | R2 | CAL-WO-01 … WO-04 |
| `_collect_work_orders` | R3 [BUG-1876] | CAL-OQ14-01 |
| `_collect_work_orders` | R3a | CAL-OQ14-02 |
| `_collect_work_orders` | R4 [BUG-1877] | CAL-OQ15-01 (pass part: CAL-WO-08) |
| `_collect_purchase_orders` | R1 | CAL-PO-03 … PO-08 |
| `_collect_purchase_orders` | R2 | CAL-PO-01 … PO-05 |
| `_collect_expense_orders` | R1 | CAL-EO-02 … EO-06 |
| `_collect_expense_orders` | R2 | CAL-EO-01 … EO-03 |
| `_collect_sales_orders` | R1 | CAL-SO-02 … SO-05 |
| `_collect_sales_orders` | R2 | CAL-SO-01 … SO-03 |
| `_collect_sales_orders` | R3 [BUG-1878] | CAL-OQ15-02 (pass part: CAL-SO-06) |
| `_collect_sales_deliveries` | R1 | CAL-SD-02 … SD-07, CAL-GE-07 |
| `_collect_sales_deliveries` | R2 | CAL-SD-01 … SD-03 |
| `_collect_invoices` | R1 | CAL-IN-02 … IN-06 |
| `_collect_invoices` | R2 | CAL-IN-01 … IN-03, CAL-GE-11 |
| `_collect_invoices` | R3 | CAL-IN-01, CAL-IN-07, CAL-IN-08 |
| `_collect_invoice_payments` | R1 | CAL-PY-03 … PY-07 |
| `_collect_invoice_payments` | R2 | CAL-PY-01, CAL-PY-02 |
| `_collect_invoice_payments` | R3 [BUG-1801] | CAL-PY-08 (pass part: CAL-PY-01) |
| `_collect_production_batches` | R1 | CAL-PB-01 … PB-03, PB-05, PB-06, PB-08 |
| `_collect_production_batches` | R2 [BUG-1807] | CAL-PB-07 (pass part: CAL-PB-04) |
| `_collect_projects` | R1 | CAL-PJ-02 … PJ-04, PJ-07, PJ-08, PJ-12 |
| `_collect_projects` | R2 [BUG-1800] | CAL-PJ-10 |
| `_collect_projects` | R3 [BUG-1806] | CAL-PJ-11 (pass part: CAL-PJ-09) |
| `_collect_projects` | R4 | CAL-PJ-01 … PJ-04, PJ-12 |
| `_collect_projects` | R5 | CAL-PJ-01, CAL-PJ-05, CAL-PJ-06 |
| `_collect_projects` | R6 [BUG-1869] | CAL-OQ5-01 … OQ5-11 |
| `calendar_service` singleton | Not specified | — |
