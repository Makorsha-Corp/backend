# Test cases — `app/services/item_summary_service.py`

> **Spec:** `tests/unit/services/item_summary_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 (2026-11-10) — `item_summary_service.verify.md` findings 1–5, 7 and spec R5b (round 3, G-V1). Changed: PRC-07 also checks the `days_30` / `days_90` min and max (finding 2; Rules + R3); US-03 gains W0 and W2 formula, batch and project lines of I1 next to one W1 line of each, and checks every count and preview (finding 3; Rules + R3). New: PS-08 (priced quantity 0.75 in all, mutant #206), OS-13 (stored subtotals 45.00 + 7.50, not quantity × price; finding 4), MF-07, MF-08 (the 999999999 stand-in from both sides, mutant #285; finding 5), PD-14 (margin 0.75; finding 7), SR-19, SR-20 (R5b: all-undated supplier; undated lines never replace a dated one, mutant #185). All new cards pass today. No card retired; no new gap.
> **Revision:** 3 (2026-11-10) — executor note (`item_summary_service.notes.md`): `sales_order_items.unit_price` and `line_total` are NOT NULL, so a sales line with no total cannot exist; OQ31-11 retired (the "empty total counts as 0" part of `_order_stats_for_item` R5a cannot be reached for sales lines). Parallel runs: `so`, `to` and `ret` store their number with the per-process suffix **GN** (Conventions); ON-04, ON-05 and RA's transfer-number card now expect `GN(...)`. No card added.
> **Revision:** 2 (2026-11-10) — spec round 2 (owner answers + Gap log G1–G9). **OQ-31 → BUG-2485:** OQ31-01 … OQ31-05 are now strict xfail (`total_spend` purchases only, new `sales_revenue`); new OQ31-06 … OQ31-09 (pass: the quantity halves that hold today and after), OQ31-10, OQ31-11 (xfail: `sales_revenue` 0 when empty or unpriced). **OQ-32 → BUG-2486:** OQ32-01 … OQ32-07, OQ32-09 unchanged (pass, the quantity rule R4 stands); OQ32-08 retitled (no workflow → open, pass, R4b); new OQ32-10, -12, -16, -17 (xfail: last status of the order's workflow) and OQ32-11, -13, -14, -15 (pass: earlier status, empty sequence, W2 / W0 workflow). `Pending:` header lines dropped. **G3:** new OL-21 … OL-30, ON-10 … ON-14, AL-04, AL-05 (strict xfail BUG-2520, the new required `workspace_id`; W0 and W2 shapes, a W1 line on a W2 order, pass-through of a given order); OL-01 now names a real W1 sales order and no longer asserts "nothing read" (the fix reads it, R5). **G2:** new AL-06, AL-07 (R3, pass). **G5 → BUG-2487:** new RA-23, RA-24. **G7:** SS-12 stays, SS-10 … SS-12 also cite `_supplier_stats` R5; new SR-17 (xfail, same order on the latest date) and SR-18 (pass, greater order id first in input). **G9:** CH-01, MF-02 also check the pick is the input row object. **G4, G6:** Conventions builders (`revi`, `ret`, **deleted line**, **deleted account**, **deleted stock**, **wf**); IV-05 uses deleted stock. G1, G8: assumptions confirmed, no card changed. No card retired.
> **Counts:** 305 cases · 195 expected-to-pass · 110 expected-to-fail (bugs; 5 non-strict) · 3 deferred

## Reviewer summary
- **Per callable:** `_dec` 6 · `_est_value` 7 · `get_summary` 15 (1 bug) · `_factory_name_map` 2 · `_machine_name_map` 1 · `_machine_location_map` 8 (4 bug) · `_inventory_rows` 13 (4 bug) · `_product_rows` 14 (4 bug) · `_machine_placements` 11 (6 bug) · `_order_stats_for_item` 13 (1 bug) + OQ-31 10 (6 bug) · `_pricing_snapshot_from_po_lines` 8 · `_pricing` 9 (3 bug) + OQ-32 17 (4 bug) · `_supplier_stats` 12 (6 bug) · `_supplier_period_snapshot` 8 (2 bug) · `_supplier_rows_from_po_lines` 20 (6 bug) · `_pick_cheapest_supplier` 7 (1 bug) · `_pick_most_frequent_supplier` 8 (2 bug) · `_usage` 30 (19 bug) · `_resolve_order_link` 30 (15 bug) · `_resolve_order_number` 14 (5 bug) · `_activity_from_ledger` 7 (2 bug) · `_recent_activity` 24 (8 bug) · DAO pass-throughs 11 (11 bug).
- **Depth:** full. This is a money and stock aggregator. As asked, these get full depth: workspace isolation (standing W0 and W2 rows on both sides of every filter; each HR-16 link shape on its own card, a W0 and a W2 variant for the factory, supplier, work-order and order-link shapes), voided POs (BUG-2521) and deleted rows, exact `Decimal` money, ties and top-N cuts, and both edges of the 30- and 90-day windows (day 30 / 31, day 90 / 91, today, tomorrow).
- **HR-15:** nothing in this module rounds (spec). The half-cent cards (EST-07, PS-07, SR-07) assert that the value stays unrounded (`2.125`, `0.375`), so a half-up or half-even `quantize` added later fails them.
- **Owner answers (2026-11-10):** OQ-31 → BUG-2485 (`total_spend` purchases only, `sales_revenue` its own figure, transfers in no money figure); OQ-32 → BUG-2486 (a line of an order in its workflow's last status is not open). Their cards keep the OQ31 / OQ32 IDs in their own sections; the quantity halves that hold today and after are pass cards there.
- **Expected-to-fail:** 110. Strict: BUG-2520 38, BUG-2522 10, BUG-2523 8, BUG-2485 6, BUG-2524 5, BUG-2526 5, BUG-2527 5, BUG-2486 4, BUG-2521 4, BUG-2525 4, BUG-2487 2, BUG-981 2, and BUG-1339, 1338, 1328, 884, 982, 977, 1326, 932, 640, 1337, 2528, 2529 1 each. Non-strict: 5 (`Author: claude`): two DB-level supplier last-price ties (SS-10, SS-11), three collation-dependent preview orders (US-10, US-11, US-13). Each non-strict group has a strict SQL `ORDER BY` alarm (SS-12, US-12, US-14).
- **Notable design choices:**
  - Name-tie cards for stock and finished goods call the helpers directly with a hand-made factory-name map (`"mill"` / `"Mill"`). Real factories with equal names would break once BUG-895's unique index lands.
  - `today` is passed as the fixed TD to `_pricing` and `_supplier_stats`. Only the `get_summary` window cards (GS-09, GS-10) and OQ31-05, OQ31-09, OQ32-17 use the real `date.today()`.
  - The resolvers' HR-16 rules are tested directly with the fix's new `workspace_id` (OL-21 …, ON-10 …, AL-04, AL-05) and through `_recent_activity` (RA-19, RA-20). Today's OL / ON / AL cards gain `workspace_id=W1.id` when the fix lands (Conventions).
  - BUG-2487 (RA-23, RA-24, `Author: claude`) keeps a zone-aware `performed_at` on the in-session machine-ledger object (flushed, not expired), the only way an aware value exists (spec G5).
  - BUG-2486 cards build a workflow of type `"test"` and a second W1 status "Completed"; a W2 or W0 workflow on a W1 order does not close it (OQ32-14, -15).
  - The `Machine #id` / `—` placement fallback is reachable only on today's bug paths, so it gets no pass card (skill: no pass card on a buggy path).
  - Regression halves: GS-13 (removed item: everything but stock still shows), PRC-04, SR-08, SR-12, US-18, OQ31-06 … OQ31-09 hold today and after the fixes.
  - MF-07 holds the spec's literal stand-in (R1: no average ranks as 999999999), so a real average above it loses a count tie to a supplier with no average. If the describer restates R1 as "no average ranks last" (verifier finding 5), MF-07 flips and becomes a bug card.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `ISM` = `app/services/item_summary_service.py`. `DEC` _dec · `EST` _est_value · `GS` get_summary · `FN` _factory_name_map · `MN` _machine_name_map · `ML` _machine_location_map · `IV` _inventory_rows · `PD` _product_rows · `MP` _machine_placements · `OS` _order_stats_for_item · `PS` _pricing_snapshot_from_po_lines · `PRC` _pricing · `SS` _supplier_stats · `SP` _supplier_period_snapshot · `SR` _supplier_rows_from_po_lines · `CH` _pick_cheapest_supplier · `MF` _pick_most_frequent_supplier · `US` _usage · `OL` _resolve_order_link · `ON` _resolve_order_number · `AL` _activity_from_ledger · `RA` _recent_activity · `DP` bugs of the DAOs reached through this service · `OQ31`, `OQ32` = cards of an owner question, answered 2026-11-10 (OQ-31 → BUG-2485, OQ-32 → BUG-2486); the IDs are kept.

**Owner answers (OQ-31, OQ-32).** The OQ31 and OQ32 sections hold the cards of the two answered questions: `total_spend` is purchases only and sales line totals go to the new `sales_revenue` (BUG-2485); a line of an order in its workflow's last status is not open (BUG-2486). Only OQ31 cards build sales-order lines, and only OQ32 cards build a workflow (**wf**).

**`workspace_id` on the resolvers (BUG-2520, spec G3).** `_resolve_order_link`, `_resolve_order_number` and `_activity_from_ledger` have no `workspace_id` parameter today. Only OL-21 … OL-30, ON-10 … ON-14, AL-04 and AL-05 pass it (strict xfail: the call raises `TypeError` today). Every other OL, ON and AL card keeps today's call; when the fix lands each gains `workspace_id=W1.id` (every row they read is in W1), with no other change.

**Imports.** `from app.services.item_summary_service import ItemSummaryService, item_summary_service, _dec, _est_value`; `NotFoundError` (`app.core.exceptions`); `InventoryTypeEnum` (`app.models.enums`) as STORAGE, DAMAGED, WASTE, SCRAP. Models from `app.models.<module>`: `factory.Factory`, `status.Status`, `account.Account`, `machine.Machine`, `item.Item`, `work_order_type.WorkOrderType`, `production_line.ProductionLine`, `purchase_order.PurchaseOrder`, `purchase_order_item.PurchaseOrderItem`, `transfer_order.TransferOrder`, `transfer_order_item.TransferOrderItem`, `sales_order.SalesOrder`, `sales_order_item.SalesOrderItem`, `expense_order.ExpenseOrder`, `work_order.WorkOrder`, `work_order_item.WorkOrderItem`, `inventory.Inventory`, `product.Product`, `machine_item.MachineItem`, `factory_section.FactorySection`, `machine_section_assignment.MachineSectionAssignment`, `production_formula.ProductionFormula`, `production_formula_item.ProductionFormulaItem`, `production_batch.ProductionBatch`, `production_batch_item.ProductionBatchItem`, `project.Project`, `project_component.ProjectComponent`, `project_component_item.ProjectComponentItem`, `inventory_ledger.InventoryLedger`, `product_ledger.ProductLedger`, `machine_item_ledger.MachineItemLedger`, `item_tag.ItemTag`, `item_tag_assignment.ItemTagAssignment`, `order_workflow.OrderWorkflow`, `PoReceiveEvent`, `PoReceiveEventItem`, `PurchaseOrderReturn`, `PurchaseOrderReturnItem` (where the models live). `Decimal`, `InvalidOperation` (`decimal`); `date`, `datetime`, `time`, `timedelta`, `timezone`; `ValidationError` (`pydantic`); `patch`; `event`, `text` (`sqlalchemy`); `os`.

**Calls.** `svc` = `item_summary_service`. `db` is the first argument, positional; every other argument by keyword, as the card writes it. `result` = what the When returns. `get_summary` returns `ItemSummaryResponse` (fields read by attribute). As the spec's rules state them: `_inventory_rows` returns `(rows, storage_total, factory_ids)`, `_product_rows` returns `(rows, total_qty)`, `_resolve_order_link` returns a 2-tuple `(order_type, order_id)`.

**Fixed values.** TD = `date(2026, 6, 30)` (passed as `today`). D(n) = `TD - timedelta(days=n)` (D(-1) = 1 July 2026). TODAY = `date.today()`, read once at the start of the test; G(n) = `TODAY - timedelta(days=n)`. NOON(d) = `datetime.combine(d, time(12, 0))`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. TS(n) = `datetime(2026, 1, 1, 12, 0, 0) + timedelta(days=n)` (naive; whole days apart, so no time-zone shift reorders two of them). MISSING = `999999999`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k` (an explicit row id; a Given row written "`id XID(k)`" passes `id=XID(k)`).

**Standing rows** (every test, no Given line; built in this order, each flushed, so within every table W0's rows have the lowest ids and W2's the highest):
- W0, W1, W2 = `make_workspace(db)`, in that order; U1 = `make_profile(db)`.
- W0: F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`; S0 = `Status(workspace_id=W0.id, name="Draft", comment="Stage")`; AC0 = `Account(workspace_id=W0.id, name="Zero Co")`; M0 = `Machine(workspace_id=W0.id, factory_id=F0.id, name="Zero Press")`; WT0 = `WorkOrderType(workspace_id=W0.id, name="Repair")`; L0 = `ProductionLine(workspace_id=W0.id, factory_id=F0.id, name="Zero Line")`; I0 = `Item(workspace_id=W0.id, name="Bolt", name_normalized="bolt", unit="pcs")`.
- W1: F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`; F2 = F1 but `name "Second Plant"`, `abbreviation "F2"`; FD = F1 but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`; S1 = `Status(workspace_id=W1.id, name="Draft", comment="Stage")`; AC1 = `Account(workspace_id=W1.id, name="Acme")`; AC2 = AC1 but `name "Beta"`; M1 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 1")`; WT1 = `WorkOrderType(workspace_id=W1.id, name="Repair")`; L1 = `ProductionLine(workspace_id=W1.id, factory_id=F1.id, name="Line One")`; I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs", description="Steel bolt", sku="B-1", created_by=U1.id)`; I2 = `Item(workspace_id=W1.id, name="Nut", name_normalized="nut", unit="pcs")`; IR = `Item(workspace_id=W1.id, name="Old Gasket", name_normalized="old gasket", unit="pcs", is_active=False)` (removed).
- W2: F9 = `Factory(workspace_id=W2.id, name="Factory Nine", abbreviation="F9")`; S9, AC9 (`name "Far Co"`), M9 (`factory_id F9.id`, `name "Far Press"`), WT9, L9 (`factory_id F9.id`, `name "Far Line"`), I9 (`name "Bolt"`, `name_normalized "bolt"`) built as their W1 counterparts with `workspace_id W2.id`.

**Given rows.** Built directly, flushed one at a time in the order written (ids rise in that order within a table). A builder's defaults are below; after "but" the card lists every other column that differs. "W2 x" / "W0 x" = builder x with `workspace_id` and every standing W1 reference replaced by its W2 / W0 counterpart (F1→F9/F0, S1→S9/S0, AC1→AC9/AC0, M1→M9/M0, WT1→WT9/WT0, L1→L9/L0) — the item stays I1 unless the card says otherwise. A text money value `"5.00"` means `Decimal("5.00")`; `None` means `None`.
- **po(no, d)** = `PurchaseOrder(workspace_id=W1.id, po_number=no, destination_type="storage", destination_id=F1.id, current_status_id=S1.id, created_by=U1.id, account_id=AC1.id, order_date=d, voided=False)`. **voided** = `voided True`, `void_note "Void"`, `voided_at T0`, `voided_by U1.id`.
- **pol(P, qty, price, sub)** = `PurchaseOrderItem(workspace_id=P.workspace_id, purchase_order_id=P.id, line_number=<1 + lines of P built before it>, item_id=I1.id, quantity_ordered=qty, unit_price=price, line_subtotal=sub, quantity_received=Decimal("0.00"), quantity_refunded=Decimal("0.00"))`.
- **to(no, at)** = `TransferOrder(workspace_id=W1.id, transfer_number=GN(no), source_location_type="storage", source_location_id=F1.id, destination_location_type="storage", destination_location_id=F2.id, current_status_id=S1.id, created_by=U1.id, created_at=at)`. **tol(T, qty)** = `TransferOrderItem(workspace_id=T.workspace_id, transfer_order_id=T.id, line_number=<as pol>, item_id=I1.id, quantity=qty)`.
- **so(no, d)** = `SalesOrder(workspace_id=W1.id, sales_order_number=GN(no), account_id=AC1.id, factory_id=F1.id, current_status_id=S1.id, created_by=U1.id, order_date=d, total_amount=Decimal("0.00"))`. **sol(S, qty, price, total)** = `SalesOrderItem(workspace_id=S.workspace_id, sales_order_id=S.id, item_id=I1.id, description="Line", quantity_ordered=qty, unit_price=price, line_total=total)`.
- **eo(no)** = `ExpenseOrder(workspace_id=W1.id, expense_number=no, expense_category="other", expense_date=TD, subtotal=Decimal("0.00"), total_amount=Decimal("20.00"), created_by=U1.id, description="Power bill")`.
- **wo(no)** = `WorkOrder(workspace_id=W1.id, work_order_number=no, title="Fix press", factory_id=F1.id, work_order_type_id=WT1.id, created_by=U1.id)`. **deleted wo** = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`. **wol(O)** = `WorkOrderItem(workspace_id=O.workspace_id, work_order_id=O.id, item_id=I1.id, quantity=Decimal("1"))`; **deleted line** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **stock(F, type, qty, avg)** = `Inventory(workspace_id=W1.id, item_id=I1.id, factory_id=F.id, inventory_type=type, qty=qty, avg_price=avg, created_by=U1.id, is_deleted=False)`. **prod(F, qty, cost, sell)** = `Product(workspace_id=W1.id, item_id=I1.id, factory_id=F.id, qty=qty, avg_cost=cost, selling_price=sell, is_available_for_sale=True)`. **place(M, qty, req)** = `MachineItem(workspace_id=W1.id, machine_id=M.id, item_id=I1.id, qty=qty, req_qty=req, defective_qty=None)`.
- **mach(name)** = `Machine(workspace_id=W1.id, factory_id=F1.id, name=name)`; **deleted machine** = `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **sec(name)** = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name=name)`; **deleted section** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **assign(M, S)** = `MachineSectionAssignment(workspace_id=W1.id, machine_id=M.id, factory_section_id=S.id)`.
- **pf(code, name)** = `ProductionFormula(workspace_id=W1.id, formula_code=code, name=name)`; **pfl(PF, role)** = `ProductionFormulaItem(workspace_id=PF.workspace_id, formula_id=PF.id, item_id=I1.id, item_role=role, quantity=2)`. **batch(no, d)** = `ProductionBatch(workspace_id=W1.id, batch_number=no, production_line_id=L1.id, batch_date=d, status="draft")`; **pbl(B, role)** = `ProductionBatchItem(workspace_id=B.workspace_id, batch_id=B.id, item_id=I1.id, item_role=role)`.
- **proj(name)** = `Project(workspace_id=W1.id, factory_id=F1.id, name=name, description="Main")`; **deleted proj** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **comp(P, name)** = `ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name=name)`; **pcl(C)** = `ProjectComponentItem(workspace_id=C.workspace_id, project_component_id=C.id, item_id=I1.id, qty=1)`.
- **ient(F, at)** = `InventoryLedger(workspace_id=W1.id, factory_id=F.id, item_id=I1.id, inventory_type=STORAGE, transaction_type="manual_add", quantity=1, qty_before=0, qty_after=1, performed_by=U1.id, performed_at=at, source_type=None, source_id=None)`. **pent(F, at)** = `ProductLedger(workspace_id=W1.id, factory_id=F.id, item_id=I1.id, transaction_type="sale", quantity=1, qty_before=5, qty_after=4, performed_at=at)`. **ment(M, at)** = `MachineItemLedger(workspace_id=W1.id, machine_id=M.id, item_id=I1.id, transaction_type="manual_add", quantity=1, unit_cost=Decimal("2.00"), total_cost=Decimal("2.00"), qty_before=4, qty_after=5, source_type="manual", performed_by=U1.id, performed_at=at)`.
- **tag(name, code)** = `ItemTag(workspace_id=W1.id, name=name, tag_code=code, color=None, icon=None, is_system_tag=False, is_active=True, usage_count=0)`; **tagged(X, T)** = `ItemTagAssignment(workspace_id=W1.id, item_id=X.id, tag_id=T.id, assigned_by=U1.id)`.
- **rev(P)** = `PoReceiveEvent(workspace_id=P.workspace_id, purchase_order_id=P.id, event_type="receive", created_at=T0)`; **revi(E, L)** = `PoReceiveEventItem(receive_event_id=E.id, po_item_id=L.id, quantity_delta=Decimal("5"))` (the table has no `workspace_id`). **ret(P, no)** = `PurchaseOrderReturn(workspace_id=P.workspace_id, purchase_order_id=P.id, return_number=GN(no), created_by=U1.id)`; **reti(R, L)** = `PurchaseOrderReturnItem(workspace_id=R.workspace_id, return_id=R.id, po_item_id=L.id, item_id=I1.id, quantity_returned=Decimal("2.00"))`.
- Accounts: **deleted account** = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id` (what the account manager's delete writes); **inactive account** = `is_active False`. **deleted stock** (an `Inventory` row) = `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **wf(seq)** = `OrderWorkflow(workspace_id=W1.id, name="PO flow", type="test", status_sequence=seq)` (`type` is free text; "test" avoids any seeded `purchase` workflow); "W2 wf" / "W0 wf" = `workspace_id W2.id` / `W0.id`. A PO joins it with `order_workflow_id WF.id`.
- **Supplier tuples** (pure helpers): `(account_id, account_name, po_id, qty, unit_price, line_subtotal, po_date)`, written with plain ints for ids and Decimal texts as above, e.g. `(1, "Acme", 10, "10.00", "5.00", "50.00", D(5))`.
- **FMAP** = `{F1.id: "Factory One", F2.id: "Second Plant", FD.id: "Old Plant"}`; **MMAP** = `{M1.id: "Press 1"}` (hand-made name maps passed to `_recent_activity`).

**Named checks.**
- **recorder** = a Given step: `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `(statement, params)`; removed with `event.remove` right after the When. `statement:` lines check `stmts`; "SELECTs reading `t`" = recorded statements starting with `SELECT` whose text contains `t`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **commit point** = `db.commit()` after the Given lines above it (a savepoint release under the `db` fixture); lines marked "(after the commit point)" run after it, unflushed unless they say so.
- **re-read X** = `db.expire_all()`, then SELECT X by id. `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call. `session:` lines check `db` directly, before anything expires it.

**xfail cards.** Strict (`pytest.mark.xfail(strict=True, reason="BUG-NNN")`) unless the Expect line says `(non-strict)`; non-strict cards are `Author: claude`. Write the call and the checks as shown.

**Externals.** None mocked; `date.today()` is not patched. **Race simulations.** None.

**Parallel runs.** `transfer_number`, `sales_order_number` and `return_number` are unique across all workspaces today (BUG-726 and siblings). **GN(n)** = `f"{n}-{os.getpid()}"`: the `to`, `so` and `ret` builders store `GN(n)` for the card's number n, and a Then line that reads such a number back expects `GN(n)`. PO, expense, work order and batch numbers are unique per workspace and are stored as written.

## `_dec`

### ISM-DEC-01 — None becomes zero
- **Rules:** `_dec` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(None)`.

**Then**
1. returns: `result == Decimal(0)`.
2. returns: `isinstance(result, Decimal)`.

### ISM-DEC-02 — a two-place Decimal keeps its places
- **Rules:** `_dec` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(Decimal("5.00"))`.

**Then**
1. returns: `str(result) == "5.00"`.

### ISM-DEC-03 — an int becomes a whole Decimal
- **Rules:** `_dec` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(3)`.

**Then**
1. returns: `str(result) == "3"`.

### ISM-DEC-04 — a float goes through its text, not its binary value
- **Rules:** `_dec` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(0.1)`.

**Then**
1. returns: `result == Decimal("0.1")`.
2. returns: `result != Decimal(0.1)`.

### ISM-DEC-05 — the int zero is a value, not empty
- **Rules:** `_dec` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(0)`.

**Then**
1. returns: `str(result) == "0"`.

### ISM-DEC-06 — text that is not a number raises
- **Rules:** `_dec` R3, Errors R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `_dec("abc")`.

**Then**
1. raises: `InvalidOperation`.

## `_est_value`

### ISM-EST-01 — no average price gives no value
- **Rules:** `_est_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _est_value(5, None)`.

**Then**
1. returns: `result is None`.

### ISM-EST-02 — zero quantity gives no value
- **Rules:** `_est_value` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _est_value(0, Decimal("2.50"))`.

**Then**
1. returns: `result is None`.

### ISM-EST-03 — negative quantity gives no value
- **Rules:** `_est_value` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _est_value(-1, Decimal("2.50"))`.

**Then**
1. returns: `result is None`.

### ISM-EST-04 — quantity one is valued
- **Rules:** `_est_value` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _est_value(1, Decimal("2.50"))`.

**Then**
1. returns: `result == Decimal("2.50")`.

### ISM-EST-05 — value is price times quantity
- **Rules:** `_est_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _est_value(7, Decimal("2.50"))`.

**Then**
1. returns: `result == Decimal("17.50")`.
2. returns: `str(result) == "17.50"`.

### ISM-EST-06 — a zero price is a price
- **Rules:** `_est_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _est_value(3, Decimal("0"))`.

**Then**
1. returns: `result is not None`.
2. returns: `result == Decimal("0")`.

### ISM-EST-07 — the value is not rounded
- **Rules:** `_est_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _est_value(3, Decimal("0.125"))`.

**Then**
1. returns: `str(result) == "0.375"`.

## `ItemSummaryService.get_summary`

### ISM-GS-01 — an unknown item is not found
- **Rules:** `get_summary` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `svc.get_summary(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 999999999 not found"`.

### ISM-GS-02 — an item of a later workspace is not found
- **Rules:** `get_summary` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (I9 is W2's "Bolt").

**When**
- `svc.get_summary(db, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.

### ISM-GS-03 — an item of an earlier workspace is not found, and nothing else is read
- **Rules:** `get_summary` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `Inventory(workspace_id=W0.id, item_id=I0.id, factory_id=F0.id, inventory_type=STORAGE, qty=7, avg_price=Decimal("1.00"), created_by=U1.id, is_deleted=False)`.
2. recorder.

**When**
- `svc.get_summary(db, item_id=I0.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Item with ID {I0.id} not found"`.
3. statement: no recorded statement contains `inventory`.
4. statement: no recorded statement contains `purchase_order_items`.
5. statement: no recorded statement contains `machine_items`.

### ISM-GS-04 — a removed item is summarised
- **Rules:** `get_summary` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Standing rows only (IR has `is_active False`).

**When**
- `result = svc.get_summary(db, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.item.id == IR.id`.
2. returns: `result.item.is_active is False`.
3. returns: `result.item.name == "Old Gasket"`.

### ISM-GS-05 — the item block carries the stored fields
- **Rules:** `get_summary` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.item.id == I1.id`, `result.item.workspace_id == W1.id`.
2. returns: `result.item.name == "Bolt"`, `result.item.description == "Steel bolt"`, `result.item.unit == "pcs"`, `result.item.sku == "B-1"`.
3. returns: `result.item.is_active is True`, `result.item.created_by == U1.id`, `result.item.updated_by is None`.
4. returns: `result.item.created_at == I1.created_at`, `result.item.updated_at == I1.updated_at`.

### ISM-GS-06 — tags are the item's active tags with their fields
- **Rules:** `get_summary` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. TR = tag("Red", "red").
2. TB = tag("Blue", "blue") but `is_active False`.
3. tagged(I1, TR).
4. tagged(I1, TB).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[t.name for t in result.item.tags] == ["Red"]`.
2. returns: `result.item.tags[0].id == TR.id`, `result.item.tags[0].tag_code == "red"`.
3. returns: `result.item.tags[0].color is None`, `result.item.tags[0].icon is None`, `result.item.tags[0].is_system_tag is False`.

### ISM-GS-07 — a removed item's tags are shown
- **Rules:** `get_summary` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TR = tag("Red", "red").
2. tagged(IR, TR).

**When**
- `result = svc.get_summary(db, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t in result.item.tags] == [TR.id]`.

### ISM-GS-08 — the KPI strip adds up the sections
- **Rules:** `get_summary` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. M2 = mach("Press 2").
2. stock(F1, STORAGE, 5, Decimal("2.00")).
3. stock(F1, DAMAGED, 2, None).
4. stock(F2, STORAGE, 3, Decimal("1.00")).
5. prod(F1, 4, Decimal("1.00"), Decimal("2.00")).
6. prod(F2, 6, Decimal("1.00"), Decimal("2.00")).
7. place(M1, 2, None).
8. place(M2, 0, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.kpis.storage_qty_total == 8`.
2. returns: `result.kpis.factory_count_with_stock == 2`.
3. returns: `result.kpis.product_qty_total == 10`.
4. returns: `result.kpis.machine_placement_count == 2`.
5. returns: `len(result.inventory_rows) == 3`, `len(result.product_rows) == 2`, `len(result.machine_placements) == 2`.

### ISM-GS-09 — the order-stat windows run from today back 30 and 90 days, both ends in
- **Rules:** `get_summary` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", G(0)); pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. PB = po("PO-B", G(30)); pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).
3. PC = po("PO-C", G(31)); pol(PC, Decimal("4.00"), Decimal("1.00"), Decimal("4.00")).
4. PD = po("PO-D", G(90)); pol(PD, Decimal("8.00"), Decimal("1.00"), Decimal("8.00")).
5. PE = po("PO-E", G(91)); pol(PE, Decimal("16.00"), Decimal("1.00"), Decimal("16.00")).
6. PF = po("PO-F", G(-1)); pol(PF, Decimal("32.00"), Decimal("1.00"), Decimal("32.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.order_stats.days_30.purchase_qty == Decimal("3.00")`.
2. returns: `result.order_stats.days_30.line_count == 2`.
3. returns: `result.order_stats.days_30.total_spend == Decimal("3.00")`.
4. returns: `result.order_stats.days_90.purchase_qty == Decimal("15.00")`.
5. returns: `result.order_stats.days_90.line_count == 4`.
6. returns: `result.order_stats.all_time.purchase_qty == Decimal("63.00")`.
7. returns: `result.order_stats.all_time.line_count == 6`.

### ISM-GS-10 — pricing and supplier windows use the same today
- **Rules:** `get_summary` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", G(30)); pol(PA, Decimal("1.00"), Decimal("9.00"), Decimal("9.00")).
2. PB = po("PO-B", G(31)) but `account_id AC2.id`; pol(PB, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.pricing.period.days_30.min_unit_price == Decimal("9.00")`.
2. returns: `result.pricing.period.days_90.min_unit_price == Decimal("1.00")`.
3. returns: `[s.account_id for s in result.supplier_stats.period.days_30.suppliers] == [AC1.id]`.
4. returns: `sorted(s.account_id for s in result.supplier_stats.period.days_90.suppliers) == sorted([AC1.id, AC2.id])`.

### ISM-GS-11 — another workspace's rows of a same-named item never reach the summary
- **Rules:** `get_summary` R6; `_inventory_rows` R1; `_order_stats_for_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `Inventory(workspace_id=W0.id, item_id=I0.id, factory_id=F0.id, inventory_type=STORAGE, qty=7, avg_price=Decimal("1.00"), created_by=U1.id, is_deleted=False)`.
2. P0 = W0 po("PO-Z", G(1)); pol(P0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00")) but `item_id I0.id`.
3. stock(F1, STORAGE, 5, Decimal("2.00")).
4. P1 = po("PO-1", G(1)); pol(P1, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
5. `Inventory(workspace_id=W2.id, item_id=I9.id, factory_id=F9.id, inventory_type=STORAGE, qty=9, avg_price=Decimal("1.00"), created_by=U1.id, is_deleted=False)`.
6. P9 = W2 po("PO-N", G(1)); pol(P9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00")) but `item_id I9.id`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.kpis.storage_qty_total == 5`.
2. returns: `result.kpis.factory_count_with_stock == 1`.
3. returns: `result.order_stats.all_time.purchase_qty == Decimal("1.00")`.
4. returns: `result.order_stats.all_time.line_count == 1`.

### ISM-GS-12 — a removed item shows no factory or machine stock
- **Rules:** `get_summary` R7 [BUG-1339]; `_inventory_rows` R8; `_machine_placements` R4
- **Kind:** bug
- **Expect:** xfail BUG-1339
- **Fails today on:** Then 2 (factory stock of the removed item is listed)

**Given**
1. SR = stock(F1, STORAGE, 5, Decimal("2.00")) but `item_id IR.id`.
2. place(M1, 2, None) but `item_id IR.id`.

**When**
- `result = svc.get_summary(db, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.item.id == IR.id`.
2. returns: `result.inventory_rows == []`.
3. returns: `result.machine_placements == []`.
4. returns: `result.kpis.storage_qty_total == 0`.
5. returns: `result.kpis.factory_count_with_stock == 0`.
6. returns: `result.kpis.machine_placement_count == 0`.
7. re-read SR: `qty == 5`, `is_deleted is False`.

### ISM-GS-13 — a removed item still shows orders, prices, suppliers, usage and history
- **Rules:** `get_summary` R7 (the part that holds today), R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = po("PO-1", G(2)); pol(P, Decimal("2.00"), Decimal("3.00"), Decimal("6.00")) but `item_id IR.id`.
2. O = wo("WO-1"); wol(O) but `item_id IR.id`.
3. ient(F1, TS(1)) but `item_id IR.id`.

**When**
- `result = svc.get_summary(db, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.order_stats.all_time.purchase_qty == Decimal("2.00")`.
2. returns: `result.pricing.last_unit_price == Decimal("3.00")`.
3. returns: `[s.account_id for s in result.supplier_stats.period.all_time.suppliers] == [AC1.id]`.
4. returns: `result.usage_counts.work_order_line_count == 1`.
5. returns: `len(result.recent_activity) == 1`.

### ISM-GS-14 — the call leaves pending changes pending and never commits or rolls back
- **Rules:** `get_summary` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. stock(F1, STORAGE, 5, Decimal("2.00")).
2. commit point.
3. (after the commit point) `I2.description = "Edited"` (not flushed).
4. (after the commit point) `db.add(Status(workspace_id=W1.id, name="Pending", comment="Stage"))` (not flushed).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)` inside spies.

**Then**
1. returns: `result.item.id == I1.id`.
2. session: `I2 in db.dirty`, `len(db.dirty) == 1`.
3. session: `len(db.new) == 1`.
4. session: `not db.deleted`.
5. mock called: `cm.call_count == 0`.
6. mock called: `rb.call_count == 0`.

### ISM-GS-15 — a failing read reaches the caller unchanged, with no rollback
- **Rules:** `get_summary` R8
- **Kind:** error
- **Author:** claude
- **Expect:** pass

**Given**
1. E = `RuntimeError("boom")`.
2. spies, and inside them `patch.object(db, "query", side_effect=E)` and `patch.object(db, "execute", side_effect=E)`.

**When**
- `svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)` inside `pytest.raises(RuntimeError)`.

**Then**
1. raises: `exc.value is E`.
2. mock called: `rb.call_count == 0`.
3. mock called: `cm.call_count == 0`.

## `ItemSummaryService._factory_name_map`

### ISM-FN-01 — every factory of the workspace, deleted and inactive included, no other workspace's
- **Rules:** `_factory_name_map` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FI = `Factory(workspace_id=W1.id, name="Idle Plant", abbreviation="IP", is_active=False)`.

**When**
- `result = svc._factory_name_map(db, W1.id)`.

**Then**
1. returns: `result == {F1.id: "Factory One", F2.id: "Second Plant", FD.id: "Old Plant", FI.id: "Idle Plant"}`.

### ISM-FN-02 — a workspace with no factories gives an empty map
- **Rules:** `_factory_name_map` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WX = `make_workspace(db)` (no factories).

**When**
- `result = svc._factory_name_map(db, WX.id)`.

**Then**
1. returns: `result == {}`.

## `ItemSummaryService._machine_name_map`

### ISM-MN-01 — every machine of the workspace, deleted included, no other workspace's
- **Rules:** `_machine_name_map` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MD = mach("Press 4") but deleted machine.

**When**
- `result = svc._machine_name_map(db, W1.id)`.

**Then**
1. returns: `result == {M1.id: "Press 1", MD.id: "Press 4"}`.

## `ItemSummaryService._machine_location_map`

### ISM-ML-01 — a machine with a section gives every location field
- **Rules:** `_machine_location_map` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. SA = sec("Bay A").
2. assign(M1, SA).

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `result[M1.id] == {"machine_name": "Press 1", "factory_section_id": SA.id, "factory_section_name": "Bay A", "factory_id": F1.id, "factory_name": "Factory One"}`.

### ISM-ML-02 — no section gives None, and other workspaces' machines have no entry
- **Rules:** `_machine_location_map` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (M0 in W0, M1 in W1 with no section, M9 in W2).

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id]["factory_section_id"] is None`, `result[M1.id]["factory_section_name"] is None`.

### ISM-ML-03 — a soft-deleted machine has no entry
- **Rules:** `_machine_location_map` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = mach("Press 4") but deleted machine.

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `set(result) == {M1.id}`.

### ISM-ML-04 — a machine of a deleted factory still has an entry
- **Rules:** `_machine_location_map` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MF = mach("Lost Press") but `factory_id FD.id`.

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `result[MF.id]["factory_id"] == FD.id`, `result[MF.id]["factory_name"] == "Old Plant"`.

### ISM-ML-05 — a machine whose factory is in a later workspace has no entry
- **Rules:** `_machine_location_map` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 2 (the machine is mapped to W2's factory)

**Given**
1. MX = mach("Stray Press") but `factory_id F9.id`.

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `M1.id in result`.
2. returns: `MX.id not in result`.

### ISM-ML-06 — a machine whose factory is in an earlier workspace has no entry
- **Rules:** `_machine_location_map` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 2 (the machine is mapped to W0's factory)

**Given**
1. MX = mach("Stray Press") but `factory_id F0.id`.

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `M1.id in result`.
2. returns: `MX.id not in result`.

### ISM-ML-07 — a section of another workspace is treated as none
- **Rules:** `_machine_location_map` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 2 (W2's section id is returned)

**Given**
1. S9X = `FactorySection(workspace_id=W2.id, factory_id=F9.id, name="Far Bay")`.
2. assign(M1, S9X).

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `result[M1.id]["factory_id"] == F1.id`, `result[M1.id]["factory_name"] == "Factory One"`.
2. returns: `result[M1.id]["factory_section_id"] is None`.
3. returns: `result[M1.id]["factory_section_name"] is None`.

### ISM-ML-08 — a soft-deleted section is treated as none, the assignment untouched
- **Rules:** `_machine_location_map` R4 [BUG-2525]
- **Kind:** bug
- **Expect:** xfail BUG-2525
- **Fails today on:** Then 3 (the deleted section's id is returned)

**Given**
1. SD = sec("Old Bay") but deleted section.
2. A = assign(M1, SD).

**When**
- `result = svc._machine_location_map(db, W1.id)`.

**Then**
1. returns: `result[M1.id]["factory_id"] == F1.id`.
2. re-read A: `factory_section_id == SD.id`.
3. returns: `result[M1.id]["factory_section_id"] is None`.
4. returns: `result[M1.id]["factory_section_name"] is None`.

## `ItemSummaryService._inventory_rows`

### ISM-IV-01 — a stock row gives every field
- **Rules:** `_inventory_rows` R2; `get_summary` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. stock(F1, STORAGE, 7, Decimal("2.50")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.inventory_rows) == 1`.
2. returns: `result.inventory_rows[0].factory_id == F1.id`, `result.inventory_rows[0].factory_name == "Factory One"`.
3. returns: `result.inventory_rows[0].inventory_type == "STORAGE"`.
4. returns: `result.inventory_rows[0].qty == 7`, `result.inventory_rows[0].avg_price == Decimal("2.50")`.
5. returns: `result.inventory_rows[0].est_value == Decimal("17.50")`.

### ISM-IV-02 — every type is listed; the storage total counts STORAGE only; any type puts a factory in the set
- **Rules:** `_inventory_rows` R3, R4, R5; `get_summary` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. stock(F1, STORAGE, 5, Decimal("2.00")).
2. stock(F1, WASTE, 1, None).
3. stock(F2, DAMAGED, 3, Decimal("1.00")).
4. stock(F2, SCRAP, 2, Decimal("1.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted((r.factory_id, r.inventory_type) for r in result.inventory_rows) == sorted([(F1.id, "STORAGE"), (F1.id, "WASTE"), (F2.id, "DAMAGED"), (F2.id, "SCRAP")])`.
2. returns: `result.kpis.storage_qty_total == 5`.
3. returns: `result.kpis.factory_count_with_stock == 2`.
4. returns: `[r.est_value for r in result.inventory_rows if r.inventory_type == "WASTE"] == [None]`.

### ISM-IV-03 — no STORAGE row gives a storage total of 0
- **Rules:** `_inventory_rows` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock(F2, DAMAGED, 3, Decimal("1.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.kpis.storage_qty_total == 0`.
2. returns: `result.kpis.factory_count_with_stock == 1`.

### ISM-IV-04 — rows with quantity 0 or below are skipped
- **Rules:** `_inventory_rows` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock(F1, STORAGE, 0, Decimal("2.00")).
2. stock(F1, DAMAGED, -2, Decimal("2.00")).
3. stock(F2, STORAGE, 1, Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(r.factory_id, r.qty) for r in result.inventory_rows] == [(F2.id, 1)]`.
2. returns: `result.kpis.storage_qty_total == 1`.
3. returns: `result.kpis.factory_count_with_stock == 1`.

### ISM-IV-05 — a soft-deleted stock row is not shown
- **Rules:** `_inventory_rows` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. stock(F1, STORAGE, 4, Decimal("2.00")) but deleted stock.
2. stock(F2, STORAGE, 2, Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.inventory_rows] == [F2.id]`.
2. returns: `result.kpis.storage_qty_total == 2`.

### ISM-IV-06 — other workspaces' stock and other items' stock are not shown
- **Rules:** `_inventory_rows` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `Inventory(workspace_id=W0.id, item_id=I0.id, factory_id=F0.id, inventory_type=STORAGE, qty=7, avg_price=Decimal("1.00"), created_by=U1.id, is_deleted=False)`.
2. stock(F1, STORAGE, 11, Decimal("1.00")) but `item_id I2.id`.
3. stock(F1, STORAGE, 5, Decimal("1.00")).
4. `Inventory(workspace_id=W2.id, item_id=I9.id, factory_id=F9.id, inventory_type=STORAGE, qty=9, avg_price=Decimal("1.00"), created_by=U1.id, is_deleted=False)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(r.factory_id, r.qty) for r in result.inventory_rows] == [(F1.id, 5)]`.
2. returns: `result.kpis.storage_qty_total == 5`.
3. returns: `result.kpis.factory_count_with_stock == 1`.

### ISM-IV-07 — a factory missing from the name map shows "Factory #id"
- **Rules:** `_inventory_rows` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock(F1, STORAGE, 3, Decimal("1.00")).

**When**
- `result = svc._inventory_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={})`.

**Then**
1. returns: `[r.factory_name for r in result[0]] == [f"Factory #{F1.id}"]`.
2. returns: `result[1] == 3`.
3. returns: `set(result[2]) == {F1.id}`.

### ISM-IV-08 — a type held as a plain string in the session is shown as its text
- **Rules:** `_inventory_rows` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock(F1, "DAMAGED", 2, Decimal("1.00")) (the type passed as the plain string `"DAMAGED"`; the row is flushed and not expired).

**When**
- `result = svc._inventory_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={F1.id: "Factory One"})`.

**Then**
1. returns: `[r.inventory_type for r in result[0]] == ["DAMAGED"]`.
2. returns: `result[1] == 0`.

### ISM-IV-09 — rows sort by factory name, then type text
- **Rules:** `_inventory_rows` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. stock(F1, STORAGE, 1, Decimal("1.00")).
2. stock(F2, WASTE, 1, Decimal("1.00")).
3. stock(F1, DAMAGED, 1, Decimal("1.00")).
4. stock(F2, SCRAP, 1, Decimal("1.00")).

**When**
- `result = svc._inventory_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={F1.id: "Beta", F2.id: "Alpha"})`.

**Then**
1. returns: `[(r.factory_name, r.inventory_type) for r in result[0]] == [("Alpha", "SCRAP"), ("Alpha", "WASTE"), ("Beta", "DAMAGED"), ("Beta", "STORAGE")]`.

### ISM-IV-10 — factory names sort case-insensitively
- **Rules:** `_inventory_rows` R7 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 ("Zeta" sorts before "apex" case-sensitively)

**Given**
1. stock(F1, STORAGE, 1, Decimal("1.00")).
2. stock(F2, STORAGE, 1, Decimal("1.00")).

**When**
- `result = svc._inventory_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={F1.id: "Zeta", F2.id: "apex"})`.

**Then**
1. returns: `[r.factory_name for r in result[0]] == ["apex", "Zeta"]`.

### ISM-IV-11 — equal factory names fall back to factory id ascending
- **Rules:** `_inventory_rows` R7 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 ("Mill" sorts before "mill" case-sensitively, putting F2 first)

**Given**
1. stock(F2, STORAGE, 1, Decimal("1.00")).
2. stock(F1, STORAGE, 1, Decimal("1.00")).

**When**
- `result = svc._inventory_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={F1.id: "mill", F2.id: "Mill"})`.

**Then**
1. returns: `[r.factory_id for r in result[0]] == [F1.id, F2.id]`.

### ISM-IV-12 — a stock row in a later workspace's factory is left out
- **Rules:** `_inventory_rows` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the row is listed as `Factory #<F9.id>`)

**Given**
1. stock(F9, STORAGE, 4, Decimal("1.00")) (a W1 row pointing at W2's factory).
2. stock(F1, STORAGE, 5, Decimal("1.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.inventory_rows] == [F1.id]`.
2. returns: `result.kpis.storage_qty_total == 5`.
3. returns: `result.kpis.factory_count_with_stock == 1`.

### ISM-IV-13 — a stock row in an earlier workspace's factory is left out
- **Rules:** `_inventory_rows` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the row is listed as `Factory #<F0.id>`)

**Given**
1. stock(F0, DAMAGED, 4, Decimal("1.00")) (a W1 row pointing at W0's factory).
2. stock(F1, STORAGE, 5, Decimal("1.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.inventory_rows] == [F1.id]`.
2. returns: `result.kpis.factory_count_with_stock == 1`.

## `ItemSummaryService._product_rows`

### ISM-PD-01 — a product row gives every field and a margin
- **Rules:** `_product_rows` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. prod(F1, 4, Decimal("1.50"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.product_rows) == 1`.
2. returns: `result.product_rows[0].factory_id == F1.id`, `result.product_rows[0].factory_name == "Factory One"`.
3. returns: `result.product_rows[0].qty == 4`, `result.product_rows[0].avg_cost == Decimal("1.50")`, `result.product_rows[0].selling_price == Decimal("2.00")`.
4. returns: `result.product_rows[0].is_available_for_sale is True`.
5. returns: `result.product_rows[0].margin_hint == Decimal("0.50")`.
6. returns: `result.kpis.product_qty_total == 4`.

### ISM-PD-02 — the margin may be negative or zero
- **Rules:** `_product_rows` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. prod(F1, 1, Decimal("3.00"), Decimal("2.00")).
2. prod(F2, 1, Decimal("2.00"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `{r.factory_id: r.margin_hint for r in result.product_rows} == {F1.id: Decimal("-1.00"), F2.id: Decimal("0.00")}`.

### ISM-PD-03 — a missing cost or price gives no margin
- **Rules:** `_product_rows` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. prod(F1, 1, None, Decimal("2.00")).
2. prod(F2, 1, Decimal("2.00"), None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `{r.factory_id: r.margin_hint for r in result.product_rows} == {F1.id: None, F2.id: None}`.

### ISM-PD-04 — not for sale is shown as False
- **Rules:** `_product_rows` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. prod(F1, 1, Decimal("1.00"), Decimal("2.00")) but `is_available_for_sale False`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.product_rows[0].is_available_for_sale is False`.

### ISM-PD-05 — rows with quantity 0 are skipped
- **Rules:** `_product_rows` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. prod(F1, 0, Decimal("1.00"), Decimal("2.00")).
2. prod(F2, 1, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.product_rows] == [F2.id]`.
2. returns: `result.kpis.product_qty_total == 1`.

### ISM-PD-06 — a negative row is skipped and no row gives a total of 0
- **Rules:** `_product_rows` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. prod(F1, -1, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.product_rows == []`.
2. returns: `result.kpis.product_qty_total == 0`.

### ISM-PD-07 — other workspaces' and other items' products are not shown
- **Rules:** `_product_rows` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `Product(workspace_id=W0.id, item_id=I0.id, factory_id=F0.id, qty=7, avg_cost=Decimal("1.00"), selling_price=Decimal("2.00"), is_available_for_sale=True)`.
2. prod(F1, 11, Decimal("1.00"), Decimal("2.00")) but `item_id I2.id`.
3. prod(F1, 5, Decimal("1.00"), Decimal("2.00")).
4. `Product(workspace_id=W2.id, item_id=I9.id, factory_id=F9.id, qty=9, avg_cost=Decimal("1.00"), selling_price=Decimal("2.00"), is_available_for_sale=True)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(r.factory_id, r.qty) for r in result.product_rows] == [(F1.id, 5)]`.
2. returns: `result.kpis.product_qty_total == 5`.

### ISM-PD-08 — a factory missing from the name map shows "Factory #id"
- **Rules:** `_product_rows` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. prod(F1, 3, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc._product_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={})`.

**Then**
1. returns: `[r.factory_name for r in result[0]] == [f"Factory #{F1.id}"]`.
2. returns: `result[1] == 3`.

### ISM-PD-09 — rows sort by factory name
- **Rules:** `_product_rows` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. prod(F1, 1, Decimal("1.00"), Decimal("2.00")).
2. prod(F2, 1, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc._product_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={F1.id: "Beta", F2.id: "Alpha"})`.

**Then**
1. returns: `[r.factory_name for r in result[0]] == ["Alpha", "Beta"]`.

### ISM-PD-10 — factory names sort case-insensitively
- **Rules:** `_product_rows` R5 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 ("Zeta" sorts before "apex" case-sensitively)

**Given**
1. prod(F1, 1, Decimal("1.00"), Decimal("2.00")).
2. prod(F2, 1, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc._product_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={F1.id: "Zeta", F2.id: "apex"})`.

**Then**
1. returns: `[r.factory_name for r in result[0]] == ["apex", "Zeta"]`.

### ISM-PD-11 — equal factory names fall back to factory id ascending
- **Rules:** `_product_rows` R5 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 ("Mill" sorts before "mill", putting F2 first)

**Given**
1. prod(F2, 1, Decimal("1.00"), Decimal("2.00")).
2. prod(F1, 1, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc._product_rows(db, item_id=I1.id, workspace_id=W1.id, factory_names={F1.id: "mill", F2.id: "Mill"})`.

**Then**
1. returns: `[r.factory_id for r in result[0]] == [F1.id, F2.id]`.

### ISM-PD-12 — a product row in a later workspace's factory is left out
- **Rules:** `_product_rows` R4 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (listed as `Factory #<F9.id>` and counted)

**Given**
1. prod(F9, 4, Decimal("1.00"), Decimal("2.00")) (a W1 row pointing at W2's factory).
2. prod(F1, 5, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.product_rows] == [F1.id]`.
2. returns: `result.kpis.product_qty_total == 5`.

### ISM-PD-13 — a product row in an earlier workspace's factory is left out
- **Rules:** `_product_rows` R4 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (listed as `Factory #<F0.id>` and counted)

**Given**
1. prod(F0, 4, Decimal("1.00"), Decimal("2.00")) (a W1 row pointing at W0's factory).
2. prod(F1, 5, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.product_rows] == [F1.id]`.
2. returns: `result.kpis.product_qty_total == 5`.

### ISM-PD-14 — a margin with a non-zero last digit stays exact
- **Rules:** `_product_rows` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. prod(F1, 1, Decimal("1.25"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.product_rows[0].margin_hint == Decimal("0.75")`.

## `ItemSummaryService._machine_placements`

### ISM-MP-01 — a placement gives every field from the stock row and the location map
- **Rules:** `_machine_placements` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. SA = sec("Bay A").
2. assign(M1, SA).
3. place(M1, 3, 5) but `defective_qty 1`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.machine_placements) == 1`.
2. returns: `result.machine_placements[0].machine_id == M1.id`, `result.machine_placements[0].machine_name == "Press 1"`.
3. returns: `result.machine_placements[0].factory_id == F1.id`, `result.machine_placements[0].factory_name == "Factory One"`.
4. returns: `result.machine_placements[0].factory_section_id == SA.id`, `result.machine_placements[0].factory_section_name == "Bay A"`.
5. returns: `result.machine_placements[0].qty == 3`, `result.machine_placements[0].req_qty == 5`, `result.machine_placements[0].defective_qty == 1`.
6. returns: `result.machine_placements[0].is_low_stock is True`.

### ISM-MP-02 — low stock only when a requirement exists and quantity is below it
- **Rules:** `_machine_placements` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = mach("Alpha"); place(MA, 2, None).
2. MB = mach("Bravo"); place(MB, 5, 5).
3. MC = mach("Charlie"); place(MC, 4, 5).
4. ME = mach("Echo"); place(ME, 0, 0).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `{p.machine_name: p.is_low_stock for p in result.machine_placements} == {"Alpha": False, "Bravo": False, "Charlie": True, "Echo": False}`.

### ISM-MP-03 — a placement holding 0 is listed and counted
- **Rules:** `_machine_placements` R1; `get_summary` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. place(M1, 0, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(p.machine_id, p.qty) for p in result.machine_placements] == [(M1.id, 0)]`.
2. returns: `result.kpis.machine_placement_count == 1`.

### ISM-MP-04 — other workspaces' and other items' placements are not shown
- **Rules:** `_machine_placements` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `MachineItem(workspace_id=W0.id, machine_id=M0.id, item_id=I0.id, qty=1, req_qty=None, defective_qty=None)`.
2. place(M1, 7, None) but `item_id I2.id`.
3. place(M1, 2, None).
4. `MachineItem(workspace_id=W2.id, machine_id=M9.id, item_id=I9.id, qty=1, req_qty=None, defective_qty=None)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(p.machine_id, p.qty) for p in result.machine_placements] == [(M1.id, 2)]`.
2. returns: `result.kpis.machine_placement_count == 1`.

### ISM-MP-05 — low stock first, then factory, section (none first), machine name
- **Rules:** `_machine_placements` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. SB = sec("Bay").
2. MA = mach("Alpha") but `factory_id F2.id`; place(MA, 1, None).
3. ME = mach("Echo"); place(ME, 1, None).
4. MB = mach("Bravo"); assign(MB, SB); place(MB, 1, None).
5. MD = mach("Delta") but `factory_id F2.id`; place(MD, 1, 5).
6. MC = mach("Charlie"); place(MC, 1, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_name for p in result.machine_placements] == ["Delta", "Charlie", "Echo", "Bravo", "Alpha"]`.

### ISM-MP-06 — machine names sort case-insensitively
- **Rules:** `_machine_placements` R5 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 ("Zeta" sorts before "apex" case-sensitively)

**Given**
1. MZ = mach("Zeta"); place(MZ, 1, None).
2. MA = mach("apex"); place(MA, 1, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_name for p in result.machine_placements] == ["apex", "Zeta"]`.

### ISM-MP-07 — equal machine names fall back to machine id ascending
- **Rules:** `_machine_placements` R5 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 ("Press" sorts before "press", putting the later machine first)

**Given**
1. MP1 = mach("press"); place(MP1, 1, None).
2. MP2 = mach("Press"); place(MP2, 1, None).
3. (M1 "Press 1" holds no placement of I1.)

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_id for p in result.machine_placements] == [MP1.id, MP2.id]`.

### ISM-MP-08 — section names sort case-insensitively
- **Rules:** `_machine_placements` R5 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 (section "Bay" sorts before "annex" case-sensitively)

**Given**
1. SB = sec("Bay"); SN = sec("annex").
2. MX = mach("Xray"); assign(MX, SB); place(MX, 1, None).
3. MY = mach("Yank"); assign(MY, SN); place(MY, 1, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_name for p in result.machine_placements] == ["Yank", "Xray"]`.

### ISM-MP-09 — factory names sort case-insensitively
- **Rules:** `_machine_placements` R5 [BUG-2522]
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 1 ("Factory One" sorts before "annex works" case-sensitively)

**Given**
1. FL = `Factory(workspace_id=W1.id, name="annex works", abbreviation="AW")`.
2. MX = mach("Xray"); place(MX, 1, None).
3. MY = mach("Yank") but `factory_id FL.id`; place(MY, 1, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_name for p in result.machine_placements] == ["Yank", "Xray"]`.

### ISM-MP-10 — a placement on another workspace's machine is left out
- **Rules:** `_machine_placements` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (shown as `Machine #<M9.id>` and counted)

**Given**
1. place(M9, 4, None) (a W1 row pointing at W2's machine).
2. place(M1, 2, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_id for p in result.machine_placements] == [M1.id]`.
2. returns: `result.kpis.machine_placement_count == 1`.

### ISM-MP-11 — a placement on a machine whose factory is another workspace's is left out
- **Rules:** `_machine_placements` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (shown with W0's factory name and counted)

**Given**
1. MX = mach("Stray Press") but `factory_id F0.id`; place(MX, 4, None).
2. place(M1, 2, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_id for p in result.machine_placements] == [M1.id]`.
2. returns: `result.kpis.machine_placement_count == 1`.

## `ItemSummaryService._order_stats_for_item`

All cards call `svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=…, to_date=…)` with the dates the card gives. No card in this section builds a sales line (OQ-31).

### ISM-OS-01 — a purchase line counts its quantity, subtotal and one line
- **Rules:** `_order_stats_for_item` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", D(5)); pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.purchase_qty == Decimal("10.00")`.
2. returns: `result.transfer_qty == 0`, `result.sales_qty == 0`.
3. returns: `result.total_quantity == Decimal("10.00")`.
4. returns: `result.total_spend == Decimal("50.00")`.
5. returns: `result.line_count == 1`.

### ISM-OS-02 — an empty subtotal adds 0; receipts and refunds are not read
- **Rules:** `_order_stats_for_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(5)).
2. pol(P, Decimal("10.00"), None, None) but `quantity_received Decimal("10.00")`.
3. pol(P, Decimal("4.00"), Decimal("1.00"), Decimal("4.00")) but `quantity_refunded Decimal("4.00")`.

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.purchase_qty == Decimal("14.00")`.
2. returns: `result.total_spend == Decimal("4.00")`.
3. returns: `result.line_count == 2`.

### ISM-OS-03 — the 30-day window includes both ends and nothing outside
- **Rules:** `_order_stats_for_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", D(30)); pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. PB = po("PO-B", D(31)); pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).
3. PC = po("PO-C", TD); pol(PC, Decimal("4.00"), Decimal("1.00"), Decimal("4.00")).
4. PE = po("PO-E", D(-1)); pol(PE, Decimal("8.00"), Decimal("1.00"), Decimal("8.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=D(30), to_date=TD)`.

**Then**
1. returns: `result.purchase_qty == Decimal("5.00")`.
2. returns: `result.line_count == 2`.
3. returns: `result.total_spend == Decimal("5.00")`.

### ISM-OS-04 — the 90-day edge: day 90 in, day 91 out
- **Rules:** `_order_stats_for_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", D(90)); pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. PB = po("PO-B", D(91)); pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=D(90), to_date=TD)`.

**Then**
1. returns: `result.purchase_qty == Decimal("1.00")`.
2. returns: `result.line_count == 1`.

### ISM-OS-05 — no order date: the date part of created_at decides; an order date wins over created_at
- **Rules:** `_order_stats_for_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PN = po("PO-N", None) but `created_at NOON(D(30))`; pol(PN, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. PM = po("PO-M", None) but `created_at NOON(D(31))`; pol(PM, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).
3. PQ = po("PO-O", D(31)) but `created_at NOON(TD)`; pol(PQ, Decimal("4.00"), Decimal("1.00"), Decimal("4.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=D(30), to_date=TD)`.

**Then**
1. returns: `result.purchase_qty == Decimal("1.00")`.
2. returns: `result.line_count == 1`.

### ISM-OS-06 — only a from date: no date filter
- **Rules:** `_order_stats_for_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", D(400)); pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. PB = po("PO-B", TD); pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=D(30), to_date=None)`.

**Then**
1. returns: `result.purchase_qty == Decimal("3.00")`.

### ISM-OS-07 — only a to date: no date filter
- **Rules:** `_order_stats_for_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", D(400)); pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. PB = po("PO-B", TD); pol(PB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=D(30))`.

**Then**
1. returns: `result.purchase_qty == Decimal("3.00")`.

### ISM-OS-08 — transfer lines add quantity and lines, no money; fractions sum exactly
- **Rules:** `_order_stats_for_item` R4, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = to("TO-1", NOON(D(5))).
2. tol(T, Decimal("2.50")).
3. tol(T, Decimal("1.25")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.transfer_qty == Decimal("3.75")`.
2. returns: `result.total_quantity == Decimal("3.75")`.
3. returns: `result.total_spend == 0`.
4. returns: `result.line_count == 2`.
5. returns: `result.purchase_qty == 0`.

### ISM-OS-09 — transfer lines are dated by created_at, both window ends in
- **Rules:** `_order_stats_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = to("TO-A", NOON(D(30))); tol(TA, Decimal("1.00")).
2. TB = to("TO-B", NOON(D(31))); tol(TB, Decimal("2.00")).
3. TC = to("TO-C", NOON(TD)); tol(TC, Decimal("4.00")).
4. TE = to("TO-E", NOON(D(-1))); tol(TE, Decimal("8.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=D(30), to_date=TD)`.

**Then**
1. returns: `result.transfer_qty == Decimal("5.00")`.
2. returns: `result.line_count == 2`.

### ISM-OS-10 — only this item's lines on this workspace's orders count
- **Rules:** `_order_stats_for_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po("PO-Z", D(5)); pol(P0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00")).
2. TZ0 = W0 to("TO-Z", NOON(D(5))) but `source_location_id F0.id`, `destination_location_id F0.id`; tol(TZ0, Decimal("7.00")).
3. P1 = po("PO-1", D(5)); pol(P1, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
4. pol(P1, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")) but `item_id I2.id`.
5. P9 = W2 po("PO-N", D(5)); pol(P9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00")).
6. T9 = W2 to("TO-N", NOON(D(5))) but `source_location_id F9.id`, `destination_location_id F9.id`; tol(T9, Decimal("9.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.purchase_qty == Decimal("1.00")`.
2. returns: `result.transfer_qty == 0`.
3. returns: `result.line_count == 1`.
4. returns: `result.total_spend == Decimal("1.00")`.

### ISM-OS-11 — nothing matching gives all zeros
- **Rules:** `_order_stats_for_item` Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.purchase_qty == 0`, `result.transfer_qty == 0`, `result.sales_qty == 0`.
2. returns: `result.total_quantity == 0`, `result.total_spend == 0`.
3. returns: `result.line_count == 0`.

### ISM-OS-12 — lines of a voided purchase order are not counted
- **Rules:** `_order_stats_for_item` R2a [BUG-2521]
- **Kind:** bug
- **Expect:** xfail BUG-2521
- **Fails today on:** Then 1 (the voided order's 100 are counted)

**Given**
1. P = po("PO-1", D(5)); pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00")).
2. PV = po("PO-V", D(5)) but voided; pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.purchase_qty == Decimal("10.00")`.
2. returns: `result.total_spend == Decimal("50.00")`.
3. returns: `result.line_count == 1`.

### ISM-OS-13 — spend is the stored line subtotal, not quantity times price
- **Rules:** `_order_stats_for_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(5)); pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("45.00")).
2. pol(P, Decimal("3.00"), Decimal("2.00"), Decimal("7.50")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.purchase_qty == Decimal("13.00")`.
2. returns: `result.total_spend == Decimal("52.50")`.
3. returns: `result.line_count == 2`.

## `ItemSummaryService._pricing_snapshot_from_po_lines`

Lines are `(quantity_ordered, unit_price)` pairs of `Decimal` (or `None` for the price).

### ISM-PS-01 — min, max and the unrounded weighted average of priced lines
- **Rules:** `_pricing_snapshot_from_po_lines` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `lines = [(Decimal("10.00"), Decimal("5.00")), (Decimal("100.00"), Decimal("1.00")), (Decimal("1.00"), Decimal("2.00")), (Decimal("10.00"), None)]`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.min_unit_price == Decimal("1.00")`.
2. returns: `result.max_unit_price == Decimal("5.00")`.
3. returns: `result.avg_unit_price_weighted == Decimal("1.369369369369369369369369369")`.

### ISM-PS-02 — an unpriced line adds no weight
- **Rules:** `_pricing_snapshot_from_po_lines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `lines = [(Decimal("10.00"), None), (Decimal("2.00"), Decimal("3.00"))]`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.avg_unit_price_weighted == Decimal("3")`.
2. returns: `result.min_unit_price == Decimal("3.00")`, `result.max_unit_price == Decimal("3.00")`.

### ISM-PS-03 — a zero-quantity line counts for min and max but not the average
- **Rules:** `_pricing_snapshot_from_po_lines` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `lines = [(Decimal("0.00"), Decimal("9.00")), (Decimal("2.00"), Decimal("3.00"))]`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.max_unit_price == Decimal("9.00")`.
2. returns: `result.min_unit_price == Decimal("3.00")`.
3. returns: `result.avg_unit_price_weighted == Decimal("3")`.

### ISM-PS-04 — only zero quantities: no average, but min and max
- **Rules:** `_pricing_snapshot_from_po_lines` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `lines = [(Decimal("0.00"), Decimal("4.00"))]`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.avg_unit_price_weighted is None`.
2. returns: `result.min_unit_price == Decimal("4.00")`, `result.max_unit_price == Decimal("4.00")`.

### ISM-PS-05 — only unpriced lines: all empty
- **Rules:** `_pricing_snapshot_from_po_lines` R1, R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `lines = [(Decimal("5.00"), None)]`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.min_unit_price is None`, `result.max_unit_price is None`, `result.avg_unit_price_weighted is None`.

### ISM-PS-06 — no lines: all empty
- **Rules:** `_pricing_snapshot_from_po_lines` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `lines = []`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.min_unit_price is None`, `result.max_unit_price is None`, `result.avg_unit_price_weighted is None`.

### ISM-PS-07 — a half-cent average stays unrounded
- **Rules:** `_pricing_snapshot_from_po_lines` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `lines = [(Decimal("1.00"), Decimal("2.00")), (Decimal("1.00"), Decimal("2.25"))]`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.avg_unit_price_weighted == Decimal("2.125")`.

### ISM-PS-08 — a priced quantity between 0 and 1 still gives an average
- **Rules:** `_pricing_snapshot_from_po_lines` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `lines = [(Decimal("0.50"), Decimal("4.00")), (Decimal("0.25"), Decimal("1.00"))]`.

**When**
- `result = svc._pricing_snapshot_from_po_lines(lines)`.

**Then**
1. returns: `result.avg_unit_price_weighted == Decimal("3")`.
2. returns: `result.min_unit_price == Decimal("1.00")`, `result.max_unit_price == Decimal("4.00")`.

## `ItemSummaryService._pricing`

All cards call `svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

### ISM-PRC-01 — last price: newest date, then the greatest line id; an older line with a higher id loses
- **Rules:** `_pricing` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1", TD); pol(P1, Decimal("1.00"), Decimal("7.00"), Decimal("7.00")).
2. P2 = po("PO-2", D(1)); pol(P2, Decimal("1.00"), Decimal("9.00"), Decimal("9.00")).
3. pol(P1, Decimal("1.00"), Decimal("6.00"), Decimal("6.00")).
4. P3 = po("PO-3", D(2)); pol(P3, Decimal("1.00"), Decimal("8.00"), Decimal("8.00")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.last_unit_price == Decimal("6.00")`.

### ISM-PRC-02 — with no order date, created_at dates the line for the last price
- **Rules:** `_pricing` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PN = po("PO-N", None) but `created_at NOON(TD)`; pol(PN, Decimal("1.00"), Decimal("4.00"), Decimal("4.00")).
2. PQ = po("PO-O", D(1)); pol(PQ, Decimal("1.00"), Decimal("7.00"), Decimal("7.00")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.last_unit_price == Decimal("4.00")`.

### ISM-PRC-03 — no lines: no last price and empty periods
- **Rules:** `_pricing` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.last_unit_price is None`.
2. returns: `result.period.all_time.min_unit_price is None`, `result.period.all_time.avg_unit_price_weighted is None`.
3. returns: `result.period.days_30.max_unit_price is None`.

### ISM-PRC-04 — the newest priced line gives the last price when an older line is unpriced
- **Rules:** `_pricing` R2, R2a (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = po("PO-A", D(2)); pol(PA, Decimal("1.00"), None, None).
2. PB = po("PO-B", TD); pol(PB, Decimal("1.00"), Decimal("5.00"), Decimal("5.00")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.last_unit_price == Decimal("5.00")`.

### ISM-PRC-05 — an unpriced newest line does not hide the last real price
- **Rules:** `_pricing` R2a [BUG-2524]
- **Kind:** bug
- **Expect:** xfail BUG-2524
- **Fails today on:** Then 1 (the newest line is unpriced, so the result is None)

**Given**
1. PA = po("PO-A", D(2)); pol(PA, Decimal("1.00"), Decimal("5.00"), Decimal("5.00")).
2. PB = po("PO-B", TD); pol(PB, Decimal("1.00"), None, None).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.last_unit_price == Decimal("5.00")`.

### ISM-PRC-06 — the three periods each cover their window, both ends in, the future in all time only
- **Rules:** `_pricing` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", TD); pol(PA, Decimal("1.00"), Decimal("9.00"), Decimal("9.00")).
2. PB = po("PO-B", D(30)); pol(PB, Decimal("1.00"), Decimal("8.00"), Decimal("8.00")).
3. PC = po("PO-C", D(31)); pol(PC, Decimal("1.00"), Decimal("2.00"), Decimal("2.00")).
4. PD = po("PO-D", D(90)); pol(PD, Decimal("1.00"), Decimal("7.00"), Decimal("7.00")).
5. PE = po("PO-E", D(91)); pol(PE, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
6. PF = po("PO-F", D(-1)); pol(PF, Decimal("1.00"), Decimal("0.50"), Decimal("0.50")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.period.days_30.min_unit_price == Decimal("8.00")`.
2. returns: `result.period.days_30.max_unit_price == Decimal("9.00")`.
3. returns: `result.period.days_90.min_unit_price == Decimal("2.00")`.
4. returns: `result.period.days_90.max_unit_price == Decimal("9.00")`.
5. returns: `result.period.all_time.min_unit_price == Decimal("0.50")`.
6. returns: `result.period.all_time.max_unit_price == Decimal("9.00")`.

### ISM-PRC-07 — only this item's lines on this workspace's orders are priced
- **Rules:** `_pricing` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po("PO-Z", TD); pol(P0, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. P1 = po("PO-1", D(3)); pol(P1, Decimal("1.00"), Decimal("5.00"), Decimal("5.00")).
3. P2 = po("PO-2", TD); pol(P2, Decimal("1.00"), Decimal("0.10"), Decimal("0.10")) but `item_id I2.id`.
4. P9 = W2 po("PO-N", TD); pol(P9, Decimal("1.00"), Decimal("9.00"), Decimal("9.00")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.last_unit_price == Decimal("5.00")`.
2. returns: `result.period.all_time.min_unit_price == Decimal("5.00")`.
3. returns: `result.period.all_time.max_unit_price == Decimal("5.00")`.
4. returns: `result.period.days_30.min_unit_price == Decimal("5.00")`, `result.period.days_30.max_unit_price == Decimal("5.00")`.
5. returns: `result.period.days_90.min_unit_price == Decimal("5.00")`, `result.period.days_90.max_unit_price == Decimal("5.00")`.

### ISM-PRC-08 — a voided order's line is left out of the prices
- **Rules:** `_pricing` R1a [BUG-2521]
- **Kind:** bug
- **Expect:** xfail BUG-2521
- **Fails today on:** Then 1 (the voided line is the newest, so its 1.00 is the last price)

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("1.00"), Decimal("5.00"), Decimal("5.00")).
2. PV = po("PO-V", TD) but voided; pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.last_unit_price == Decimal("5.00")`.
2. returns: `result.period.all_time.min_unit_price == Decimal("5.00")`.

### ISM-PRC-09 — a voided order's open line is not open
- **Rules:** `_pricing` R4a [BUG-2521]
- **Kind:** bug
- **Expect:** xfail BUG-2521
- **Fails today on:** Then 1 (the voided line is counted: 2 open lines)

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.
2. PV = po("PO-V", D(3)) but voided; pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("6.00")`.

## `ItemSummaryService._supplier_stats`

All cards call `svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`. **accts(snap)** = `sorted(s.account_id for s in snap.suppliers)`.

### ISM-SS-01 — each supplier's figures and both highlights
- **Rules:** `_supplier_stats` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = po("PO-A", D(3)); pol(PA, Decimal("10.00"), Decimal("5.00"), Decimal("50.00")).
2. PB = po("PO-B", D(4)) but `account_id AC2.id`; pol(PB, Decimal("4.00"), Decimal("2.00"), Decimal("8.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `[(s.account_id, s.account_name, s.order_count, s.total_qty, s.total_spend) for s in result.period.all_time.suppliers] == [(AC1.id, "Acme", 1, Decimal("10.00"), Decimal("50.00")), (AC2.id, "Beta", 1, Decimal("4.00"), Decimal("8.00"))]`.
2. returns: `result.period.all_time.highlights.cheapest.account_id == AC2.id`.
3. returns: `result.period.all_time.highlights.most_frequent.account_id == AC2.id`.

### ISM-SS-02 — an order with no supplier is left out
- **Rules:** `_supplier_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)) but `account_id None`; pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.period.all_time.suppliers == []`.
2. returns: `result.period.all_time.highlights.cheapest is None`, `result.period.all_time.highlights.most_frequent is None`.

### ISM-SS-03 — the 30-day period: day 30 in, day 31 out
- **Rules:** `_supplier_stats` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A", D(30)); pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. PB = po("PO-B", D(31)) but `account_id AC2.id`; pol(PB, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `accts(result.period.days_30) == [AC1.id]`.
2. returns: `accts(result.period.days_90) == sorted([AC1.id, AC2.id])`.

### ISM-SS-04 — the 90-day period: day 90 in, day 91 out; a future order in all time only
- **Rules:** `_supplier_stats` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AC3 = `Account(workspace_id=W1.id, name="Gamma")`.
2. PA = po("PO-A", D(90)); pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
3. PB = po("PO-B", D(91)) but `account_id AC2.id`; pol(PB, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
4. PC = po("PO-C", D(-1)) but `account_id AC3.id`; pol(PC, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `accts(result.period.days_90) == [AC1.id]`.
2. returns: `accts(result.period.all_time) == sorted([AC1.id, AC2.id, AC3.id])`.

### ISM-SS-05 — a deleted and an inactive supplier are listed under their names
- **Rules:** `_supplier_stats` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. ACD = `Account(workspace_id=W1.id, name="Gone Co")` but deleted account.
2. ACI = `Account(workspace_id=W1.id, name="Idle Co")` but inactive account.
3. PA = po("PO-A", D(3)) but `account_id ACD.id`; pol(PA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
4. PB = po("PO-B", D(3)) but `account_id ACI.id`; pol(PB, Decimal("1.00"), Decimal("2.00"), Decimal("2.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `sorted(s.account_name for s in result.period.all_time.suppliers) == ["Gone Co", "Idle Co"]`.

### ISM-SS-06 — other workspaces' orders and other items are not listed
- **Rules:** `_supplier_stats` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po("PO-Z", D(3)); pol(P0, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. P1 = po("PO-1", D(3)); pol(P1, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
3. P2 = po("PO-2", D(3)) but `account_id AC2.id`; pol(P2, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")) but `item_id I2.id`.
4. P9 = W2 po("PO-N", D(3)); pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `accts(result.period.all_time) == [AC1.id]`.

### ISM-SS-07 — a supplier of a later workspace on this workspace's order is left out
- **Rules:** `_supplier_stats` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 ("Far Co" is listed)

**Given**
1. P1 = po("PO-1", D(3)); pol(P1, Decimal("1.00"), Decimal("5.00"), Decimal("5.00")).
2. PX = po("PO-X", D(3)) but `account_id AC9.id`; pol(PX, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `accts(result.period.all_time) == [AC1.id]`.
2. returns: `result.period.all_time.highlights.cheapest.account_id == AC1.id`.

### ISM-SS-08 — a supplier of an earlier workspace on this workspace's order is left out
- **Rules:** `_supplier_stats` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 ("Zero Co" is listed)

**Given**
1. P1 = po("PO-1", D(3)); pol(P1, Decimal("1.00"), Decimal("5.00"), Decimal("5.00")).
2. PX = po("PO-X", D(3)) but `account_id AC0.id`; pol(PX, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `accts(result.period.all_time) == [AC1.id]`.

### ISM-SS-09 — a voided order's supplier line is left out
- **Rules:** `_supplier_stats` R2a [BUG-2521]
- **Kind:** bug
- **Expect:** xfail BUG-2521
- **Fails today on:** Then 1 (Beta from the voided order is listed)

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00")).
2. PV = po("PO-V", D(3)) but voided, `account_id AC2.id`; pol(PV, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `accts(result.period.all_time) == [AC1.id]`.
2. returns: `result.period.all_time.highlights.cheapest.account_id == AC1.id`.

### ISM-SS-10 — a supplier's last price on a shared date comes from the greatest order id
- **Rules:** `_supplier_rows_from_po_lines` R6, `_supplier_stats` R5 [BUG-2523]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2523 (non-strict)
- **Fails today on:** Then 1 (the first line the unordered query returns gives the price)

**Given**
1. PA = po("PO-A", D(1)); pol(PA, Decimal("1.00"), Decimal("3.00"), Decimal("3.00")).
2. PB = po("PO-B", D(1)); pol(PB, Decimal("1.00"), Decimal("4.00"), Decimal("4.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.period.all_time.suppliers[0].last_unit_price == Decimal("4.00")`.

### ISM-SS-11 — within one order on the latest date, the greatest line id gives the price
- **Rules:** `_supplier_rows_from_po_lines` R6, `_supplier_stats` R5 [BUG-2523]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2523 (non-strict)
- **Fails today on:** Then 1 (the first line the unordered query returns gives the price)

**Given**
1. P = po("PO-1", D(1)).
2. pol(P, Decimal("1.00"), Decimal("3.00"), Decimal("3.00")).
3. pol(P, Decimal("1.00"), Decimal("4.00"), Decimal("4.00")).

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.period.all_time.suppliers[0].last_unit_price == Decimal("4.00")`.

### ISM-SS-12 — the supplier query has an ORDER BY
- **Rules:** `_supplier_stats` R5, `_supplier_period_snapshot` R3, `_supplier_rows_from_po_lines` R6 [BUG-2523] (HR-6 line; spec G7: the query is ordered)
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 2 (the supplier query has no ORDER BY)

**Given**
1. P = po("PO-1", D(1)); pol(P, Decimal("1.00"), Decimal("3.00"), Decimal("3.00")).
2. recorder.

**When**
- `result = svc._supplier_stats(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `accts(result.period.all_time) == [AC1.id]`.
2. statement: the recorded SELECT reading `purchase_order_items` and `accounts` contains `ORDER BY`.

## `ItemSummaryService._supplier_period_snapshot`

Rows are supplier tuples (Conventions). All cards call `svc._supplier_period_snapshot(rows, today=TD, days=…)`. **ids(snap)** = `[s.account_id for s in snap.suppliers]`.

### ISM-SP-01 — a window keeps rows from today back n days, both ends in, nothing in the future
- **Rules:** `_supplier_period_snapshot` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "A", 10, "1.00", "1.00", "1.00", D(30)), (2, "B", 11, "1.00", "1.00", "1.00", D(31)), (3, "C", 12, "1.00", "1.00", "1.00", TD), (4, "D", 13, "1.00", "1.00", "1.00", D(-1))]` (texts as Decimals).

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=30)`.

**Then**
1. returns: `sorted(ids(result)) == [1, 3]`.

### ISM-SP-02 — no days keeps every row, future included
- **Rules:** `_supplier_period_snapshot` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "A", 10, "1.00", "1.00", "1.00", D(400)), (4, "D", 13, "1.00", "1.00", "1.00", D(-1))]` (texts as Decimals).

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=None)`.

**Then**
1. returns: `sorted(ids(result)) == [1, 4]`.

### ISM-SP-03 — a row with no date is left out of a window
- **Rules:** `_supplier_period_snapshot` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "A", 10, "1.00", "1.00", "1.00", None), (2, "B", 11, "1.00", "1.00", "1.00", TD)]` (texts as Decimals).

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=30)`.

**Then**
1. returns: `ids(result) == [2]`.

### ISM-SP-04 — suppliers sort by spend, high to low, at most 10
- **Rules:** `_supplier_period_snapshot` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(k, f"S{k}", 100 + k, "1.00", f"{k}.00", f"{k}.00", TD) for k in range(1, 12)]` (11 suppliers; supplier k spends k.00; texts as Decimals).

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=None)`.

**Then**
1. returns: `ids(result) == [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]`.

### ISM-SP-05 — highlights look at every supplier, not only the top 10
- **Rules:** `_supplier_period_snapshot` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(k, f"S{k}", 100 + k, "1.00", f"{k}.00", f"{k}.00", TD) for k in range(2, 12)]` (10 suppliers, spends 2.00 … 11.00; texts as Decimals).
2. append `(1, "S1", 201, "1.00", "0.25", "0.25", TD)` and `(1, "S1", 202, "1.00", "0.25", "0.25", TD)` (supplier 1: spend 0.50, two orders, price 0.25).

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=None)`.

**Then**
1. returns: `1 not in ids(result)`.
2. returns: `result.highlights.cheapest.account_id == 1`.
3. returns: `result.highlights.most_frequent.account_id == 1`.

### ISM-SP-06 — no rows: no highlights, no suppliers
- **Rules:** `_supplier_period_snapshot` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = []`.

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=30)`.

**Then**
1. returns: `result.suppliers == []`.
2. returns: `result.highlights.cheapest is None`, `result.highlights.most_frequent is None`.

### ISM-SP-07 — equal spend sorts by account id ascending
- **Rules:** `_supplier_period_snapshot` R3 [BUG-2523]
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 1 (ties keep input order: 7 before 3)

**Given**
1. `rows = [(7, "S7", 10, "1.00", "5.00", "5.00", TD), (3, "S3", 11, "1.00", "5.00", "5.00", TD)]` (texts as Decimals).

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=None)`.

**Then**
1. returns: `ids(result) == [3, 7]`.

### ISM-SP-08 — a tie at tenth place keeps the lower account id
- **Rules:** `_supplier_period_snapshot` R3 [BUG-2523]
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 1 (supplier 20 comes first in the input and takes tenth place)

**Given**
1. `rows = [(k, f"S{k}", 100 + k, "1.00", f"{k}0.00", f"{k}0.00", TD) for k in range(1, 10)]` (9 suppliers, spends 10.00 … 90.00; texts as Decimals).
2. append `(20, "S20", 300, "1.00", "1.00", "1.00", TD)` then `(15, "S15", 301, "1.00", "1.00", "1.00", TD)`.

**When**
- `result = svc._supplier_period_snapshot(rows, today=TD, days=None)`.

**Then**
1. returns: `ids(result)[9] == 15`.
2. returns: `20 not in ids(result)`.

## `ItemSummaryService._supplier_rows_from_po_lines`

Rows are supplier tuples (Conventions; texts as Decimals). All cards call `result = svc._supplier_rows_from_po_lines(rows)`.

### ISM-SR-01 — one row per supplier: orders, quantity, spend, average, last date and price
- **Rules:** `_supplier_rows_from_po_lines` R1, R3, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "10.00", "5.00", "50.00", D(5)), (1, "Acme", 11, "3.00", "4.00", "12.00", D(2)), (1, "Acme", 10, "2.00", "5.00", "10.00", D(5))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].account_id == 1`, `result[0].order_count == 2`.
3. returns: `result[0].total_qty == Decimal("15.00")`, `result[0].total_spend == Decimal("72.00")`.
4. returns: `result[0].avg_unit_price_weighted == Decimal("4.8")`.
5. returns: `result[0].last_order_date == D(2)`, `result[0].last_unit_price == Decimal("4.00")`.

### ISM-SR-02 — a row with no account is skipped
- **Rules:** `_supplier_rows_from_po_lines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(None, "Nobody", 10, "1.00", "1.00", "1.00", D(1)), (2, "Beta", 11, "1.00", "1.00", "1.00", D(1))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `[r.account_id for r in result] == [2]`.

### ISM-SR-03 — the name is the last non-empty name seen
- **Rules:** `_supplier_rows_from_po_lines` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "1.00", "1.00", "1.00", D(3)), (1, "Acme Ltd", 11, "1.00", "1.00", "1.00", D(2)), (1, "", 12, "1.00", "1.00", "1.00", D(1))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].account_name == "Acme Ltd"`.

### ISM-SR-04 — no name at all gives "Account #id"
- **Rules:** `_supplier_rows_from_po_lines` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(7, "", 10, "1.00", "1.00", "1.00", D(3)), (7, None, 11, "1.00", "1.00", "1.00", D(2))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].account_name == "Account #7"`.

### ISM-SR-05 — an empty subtotal adds 0 to spend; the average uses quantity times price
- **Rules:** `_supplier_rows_from_po_lines` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "10.00", "5.00", "50.00", D(3)), (1, "Acme", 11, "4.00", "2.00", None, D(4))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].total_spend == Decimal("50.00")`.
2. returns: `result[0].total_qty == Decimal("14.00")`.
3. returns: `result[0].avg_unit_price_weighted == Decimal("4.142857142857142857142857143")`.

### ISM-SR-06 — total quantity 0 gives no average
- **Rules:** `_supplier_rows_from_po_lines` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "0.00", "5.00", "0.00", D(3))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].avg_unit_price_weighted is None`.

### ISM-SR-07 — a half-cent average stays unrounded
- **Rules:** `_supplier_rows_from_po_lines` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "1.00", "2.00", "2.00", D(3)), (1, "Acme", 11, "1.00", "2.25", "2.25", D(4))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].avg_unit_price_weighted == Decimal("2.125")`.

### ISM-SR-08 — an unpriced line still counts in quantity, spend and orders
- **Rules:** `_supplier_rows_from_po_lines` R3, R4a (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "10.00", "5.00", "50.00", D(6)), (1, "Acme", 11, "10.00", None, None, D(5))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].total_qty == Decimal("20.00")`.
2. returns: `result[0].total_spend == Decimal("50.00")`.
3. returns: `result[0].order_count == 2`.

### ISM-SR-09 — the average leaves unpriced lines out
- **Rules:** `_supplier_rows_from_po_lines` R4a [BUG-2524]
- **Kind:** bug
- **Expect:** xfail BUG-2524
- **Fails today on:** Then 1 (the unpriced 10 count at 0: average 2.5)

**Given**
1. `rows = [(1, "Acme", 10, "10.00", "5.00", "50.00", D(6)), (1, "Acme", 11, "10.00", None, None, D(5))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].avg_unit_price_weighted == Decimal("5")`.

### ISM-SR-10 — only unpriced lines: no average
- **Rules:** `_supplier_rows_from_po_lines` R4a [BUG-2524]
- **Kind:** bug
- **Expect:** xfail BUG-2524
- **Fails today on:** Then 1 (today the average is 0)

**Given**
1. `rows = [(1, "Acme", 10, "10.00", None, None, D(5))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].avg_unit_price_weighted is None`.

### ISM-SR-11 — the last date is the newest line's date, wherever it sits in the input
- **Rules:** `_supplier_rows_from_po_lines` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 11, "1.00", "4.00", "4.00", D(2)), (1, "Acme", 12, "1.00", "6.00", "6.00", D(8))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_order_date == D(2)`.
2. returns: `result[0].last_unit_price == Decimal("4.00")`.

### ISM-SR-12 — an unpriced newest line still sets the last date
- **Rules:** `_supplier_rows_from_po_lines` R5, R5a (the part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 11, "1.00", None, None, D(2))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_order_date == D(2)`.

### ISM-SR-13 — the last price comes from the newest priced line
- **Rules:** `_supplier_rows_from_po_lines` R5a [BUG-2524]
- **Kind:** bug
- **Expect:** xfail BUG-2524
- **Fails today on:** Then 1 (the unpriced newest line gives 0)

**Given**
1. `rows = [(1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 11, "1.00", None, None, D(2))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_unit_price == Decimal("5.00")`.

### ISM-SR-14 — no priced line: no last price
- **Rules:** `_supplier_rows_from_po_lines` R5a [BUG-2524]
- **Kind:** bug
- **Expect:** xfail BUG-2524
- **Fails today on:** Then 1 (today 0)

**Given**
1. `rows = [(1, "Acme", 10, "1.00", None, None, D(2))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_unit_price is None`.

### ISM-SR-15 — on a shared latest date the greater order id gives the price
- **Rules:** `_supplier_rows_from_po_lines` R6 [BUG-2523]
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 1 (the first line seen on that date keeps the price: 3.00)

**Given**
1. `rows = [(1, "Acme", 8, "1.00", "3.00", "3.00", D(1)), (1, "Acme", 9, "1.00", "4.00", "4.00", D(1))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_unit_price == Decimal("4.00")`.

### ISM-SR-16 — no rows: no suppliers
- **Rules:** `_supplier_rows_from_po_lines` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = []`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result == []`.

### ISM-SR-17 — two lines of one order on the latest date: the later one in input order gives the price
- **Rules:** `_supplier_rows_from_po_lines` R6 [BUG-2523]
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 1 (the first line seen on that date keeps the price: 3.00)

**Given**
1. `rows = [(1, "Acme", 9, "1.00", "3.00", "3.00", D(1)), (1, "Acme", 9, "1.00", "4.00", "4.00", D(1))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_unit_price == Decimal("4.00")`.

### ISM-SR-18 — on a shared latest date the greater order id wins even when it comes first
- **Rules:** `_supplier_rows_from_po_lines` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 9, "1.00", "4.00", "4.00", D(1)), (1, "Acme", 8, "1.00", "3.00", "3.00", D(1))]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_unit_price == Decimal("4.00")`.
2. returns: `result[0].last_order_date == D(1)`.

### ISM-SR-19 — a supplier whose lines all have no date: no last date and no last price
- **Rules:** `_supplier_rows_from_po_lines` R5b, R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 10, "2.00", "5.00", "10.00", None), (1, "Acme", 11, "3.00", "4.00", "12.00", None)]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].order_count == 2`, `result[0].total_qty == Decimal("5.00")`, `result[0].total_spend == Decimal("22.00")`.
3. returns: `result[0].avg_unit_price_weighted == Decimal("4.4")`.
4. returns: `result[0].last_order_date is None`, `result[0].last_unit_price is None`.

### ISM-SR-20 — an undated line never replaces a dated line's date or price
- **Rules:** `_supplier_rows_from_po_lines` R5b, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [(1, "Acme", 11, "1.00", "9.00", "9.00", None), (1, "Acme", 10, "1.00", "5.00", "5.00", D(5)), (1, "Acme", 12, "1.00", "7.00", "7.00", None)]`.

**When**
- `result = svc._supplier_rows_from_po_lines(rows)`.

**Then**
1. returns: `result[0].last_order_date == D(5)`.
2. returns: `result[0].last_unit_price == Decimal("5.00")`.
3. returns: `result[0].order_count == 3`, `result[0].total_qty == Decimal("3.00")`.

## `ItemSummaryService._pick_cheapest_supplier`

Each Given builds `rows = svc._supplier_rows_from_po_lines(tuples)` from the supplier tuples shown (texts as Decimals); the input order of suppliers is the order of their first tuple.

### ISM-CH-01 — the lowest average wins
- **Rules:** `_pick_cheapest_supplier` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `tuples = [(1, "A", 10, "1.00", "5.00", "5.00", TD), (2, "B", 11, "1.00", "3.00", "3.00", TD)]`.

**When**
- `result = svc._pick_cheapest_supplier(rows)`.

**Then**
1. returns: `result.account_id == 2`.
2. returns: `result is next(r for r in rows if r.account_id == 2)`.

### ISM-CH-02 — equal averages: more orders wins
- **Rules:** `_pick_cheapest_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(1, "A", 10, "1.00", "4.00", "4.00", TD), (2, "B", 11, "1.00", "4.00", "4.00", TD), (2, "B", 12, "1.00", "4.00", "4.00", TD)]`.

**When**
- `result = svc._pick_cheapest_supplier(rows)`.

**Then**
1. returns: `result.account_id == 2`.

### ISM-CH-03 — a supplier with no average is not a candidate
- **Rules:** `_pick_cheapest_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(1, "A", 10, "0.00", "1.00", "0.00", TD), (2, "B", 11, "1.00", "9.00", "9.00", TD)]`.

**When**
- `result = svc._pick_cheapest_supplier(rows)`.

**Then**
1. returns: `result.account_id == 2`.

### ISM-CH-04 — an average of 0.00 is a real price and wins
- **Rules:** `_pick_cheapest_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(2, "B", 10, "1.00", "1.00", "1.00", TD), (1, "A", 11, "5.00", "0.00", "0.00", TD)]`.

**When**
- `result = svc._pick_cheapest_supplier(rows)`.

**Then**
1. returns: `result.account_id == 1`.

### ISM-CH-05 — no candidate gives None
- **Rules:** `_pick_cheapest_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(1, "A", 10, "0.00", "1.00", "0.00", TD)]`.

**When**
- `result = svc._pick_cheapest_supplier(rows)`.

**Then**
1. returns: `result is None`.

### ISM-CH-06 — an empty list gives None
- **Rules:** `_pick_cheapest_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = []` (no helper call).

**When**
- `result = svc._pick_cheapest_supplier(rows)`.

**Then**
1. returns: `result is None`.

### ISM-CH-07 — a full tie goes to the lowest account id
- **Rules:** `_pick_cheapest_supplier` R2 [BUG-2523]
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 1 (the first in input order, 7, wins)

**Given**
1. `tuples = [(7, "S7", 10, "1.00", "4.00", "4.00", TD), (3, "S3", 11, "1.00", "4.00", "4.00", TD)]`.

**When**
- `result = svc._pick_cheapest_supplier(rows)`.

**Then**
1. returns: `result.account_id == 3`.

## `ItemSummaryService._pick_most_frequent_supplier`

Each Given builds `rows` as in the section above.

### ISM-MF-01 — an empty list gives None
- **Rules:** `_pick_most_frequent_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = []` (no helper call).

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result is None`.

### ISM-MF-02 — more orders wins over a lower price
- **Rules:** `_pick_most_frequent_supplier` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `tuples = [(2, "B", 10, "1.00", "1.00", "1.00", TD), (1, "A", 11, "1.00", "9.00", "9.00", TD), (1, "A", 12, "1.00", "9.00", "9.00", TD)]`.

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result.account_id == 1`.
2. returns: `result is next(r for r in rows if r.account_id == 1)`.

### ISM-MF-03 — equal order counts: the lower average wins
- **Rules:** `_pick_most_frequent_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(1, "A", 10, "1.00", "5.00", "5.00", TD), (2, "B", 11, "1.00", "3.00", "3.00", TD)]`.

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result.account_id == 2`.

### ISM-MF-04 — no average ranks last on a count tie
- **Rules:** `_pick_most_frequent_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(1, "A", 10, "0.00", "1.00", "0.00", TD), (2, "B", 11, "1.00", "7.00", "7.00", TD)]`.

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result.account_id == 2`.

### ISM-MF-05 — an average of exactly 0 wins a count tie
- **Rules:** `_pick_most_frequent_supplier` R2 [BUG-2523]
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 1 (0 is falsy and ranks as 999999999, so supplier 1 wins)

**Given**
1. `tuples = [(1, "A", 10, "1.00", "5.00", "5.00", TD), (2, "B", 11, "1.00", "0.00", "0.00", TD)]`.

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result.account_id == 2`.

### ISM-MF-06 — a full tie goes to the lowest account id
- **Rules:** `_pick_most_frequent_supplier` R2 [BUG-2523]
- **Kind:** bug
- **Expect:** xfail BUG-2523
- **Fails today on:** Then 1 (the first in input order, 7, wins)

**Given**
1. `tuples = [(7, "S7", 10, "1.00", "4.00", "4.00", TD), (3, "S3", 11, "1.00", "4.00", "4.00", TD)]`.

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result.account_id == 3`.

### ISM-MF-07 — an average above the 999999999 stand-in loses a count tie to no average
- **Rules:** `_pick_most_frequent_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(1, "A", 10, "1.00", "999999999.50", "999999999.50", TD), (2, "B", 11, "0.00", "1.00", "0.00", TD)]`.

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result.account_id == 2`.

### ISM-MF-08 — an average just below the 999999999 stand-in beats no average
- **Rules:** `_pick_most_frequent_supplier` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tuples = [(2, "B", 11, "0.00", "1.00", "0.00", TD), (1, "A", 10, "1.00", "999999998.50", "999999998.50", TD)]`.

**When**
- `result = svc._pick_most_frequent_supplier(rows)`.

**Then**
1. returns: `result.account_id == 1`.

## `ItemSummaryService._usage`

All cards read `_usage` through `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`; **uc** = `result.usage_counts`, **ud** = `result.usage_details`.

### ISM-US-01 — each count is a line count; one item used twice in a formula counts 2
- **Rules:** `_usage` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PF = pf("FM-1", "Mix"); pfl(PF, "input"); pfl(PF, "output").
2. B = batch("B-1", TD); pbl(B, "input").
3. P = proj("Bridge"); C = comp(P, "Deck"); pcl(C).
4. O = wo("WO-1"); wol(O).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.formula_count == 2`.
2. returns: `uc.batch_line_count == 1`.
3. returns: `uc.project_component_count == 1`.
4. returns: `uc.work_order_line_count == 1`.

### ISM-US-02 — an inactive formula and a cancelled batch count and show
- **Rules:** `_usage` R1, R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. PF = pf("FM-1", "Mix") but `is_active False`; pfl(PF, "input").
2. B = batch("B-1", TD) but `status "cancelled"`, `updated_by U1.id`; pbl(B, "output").

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.formula_count == 1`.
2. returns: `uc.batch_line_count == 1`.
3. returns: `[f.formula_id for f in ud.formulas] == [PF.id]`.
4. returns: `[(b.batch_id, b.status) for b in ud.batches] == [(B.id, "cancelled")]`.

### ISM-US-03 — lines of other workspaces and of other items neither count nor show
- **Rules:** `_usage` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = W0 wo("WO-Z"); wol(O0) (a W0 line of I1).
2. PF0 = W0 pf("FM-Z", "Zero Mix"); pfl(PF0, "input") but `item_id I0.id`.
3. PF0X = W0 pf("FM-Y", "Zero Blend"); pfl(PF0X, "input") (a W0 line of I1).
4. B0 = W0 batch("B-Z", TD); pbl(B0, "input").
5. P0 = W0 proj("Zero Bridge"); C0 = comp(P0, "Zero Deck"); pcl(C0).
6. O1 = wo("WO-1"); wol(O1); wol(O1) but `item_id I2.id`.
7. PF1 = pf("FM-1", "Mix"); pfl(PF1, "input").
8. B1 = batch("B-1", TD); pbl(B1, "input").
9. P1 = proj("Bridge"); C1 = comp(P1, "Deck"); pcl(C1).
10. O9 = W2 wo("WO-N"); wol(O9) (a W2 line of I1).
11. PF9 = W2 pf("FM-N", "Far Mix"); pfl(PF9, "input").
12. B9 = W2 batch("B-N", TD); pbl(B9, "input").
13. P9 = W2 proj("Far Bridge"); C9 = comp(P9, "Far Deck"); pcl(C9).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.work_order_line_count == 1`.
2. returns: `uc.formula_count == 1`.
3. returns: `uc.batch_line_count == 1`.
4. returns: `uc.project_component_count == 1`.
5. returns: `[w.work_order_id for w in ud.work_orders] == [O1.id]`.
6. returns: `[f.formula_id for f in ud.formulas] == [PF1.id]`.
7. returns: `[b.batch_id for b in ud.batches] == [B1.id]`.
8. returns: `[(p.project_id, p.component_id) for p in ud.projects] == [(P1.id, C1.id)]`.

### ISM-US-04 — preview entries carry their fields
- **Rules:** `_usage` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. PF = pf("FM-1", "Mix"); pfl(PF, "input").
2. B = batch("B-1", TD); pbl(B, "output").
3. P = proj("Bridge"); C = comp(P, "Deck"); pcl(C).
4. O = wo("WO-1"); wol(O).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(f.formula_id, f.formula_code, f.name, f.item_role) for f in ud.formulas] == [(PF.id, "FM-1", "Mix", "input")]`.
2. returns: `[(b.batch_id, b.batch_number, b.item_role, b.status) for b in ud.batches] == [(B.id, "B-1", "output", "draft")]`.
3. returns: `[(p.project_id, p.project_name, p.component_id, p.component_name) for p in ud.projects] == [(P.id, "Bridge", C.id, "Deck")]`.
4. returns: `[(w.work_order_id, w.work_order_number, w.title) for w in ud.work_orders] == [(O.id, "WO-1", "Fix press")]`.

### ISM-US-05 — work orders: five newest by line created_at
- **Rules:** `_usage` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = wo("WO-A"); wol(OA) but `created_at TS(3)`.
2. OB = wo("WO-B"); wol(OB) but `created_at TS(6)`.
3. OC = wo("WO-C"); wol(OC) but `created_at TS(1)`.
4. OD = wo("WO-D"); wol(OD) but `created_at TS(5)`.
5. OE = wo("WO-E"); wol(OE) but `created_at TS(2)`.
6. OF = wo("WO-F"); wol(OF) but `created_at TS(4)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[w.work_order_number for w in ud.work_orders] == ["WO-B", "WO-D", "WO-F", "WO-A", "WO-E"]`.
2. returns: `uc.work_order_line_count == 6`.

### ISM-US-06 — work orders: equal created_at falls back to line id high to low
- **Rules:** `_usage` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OC = wo("WO-C"); wol(OC) but `created_at TS(2)`.
2. OA = wo("WO-A"); wol(OA) but `created_at TS(1)`.
3. OB = wo("WO-B"); wol(OB) but `created_at TS(1)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[w.work_order_number for w in ud.work_orders] == ["WO-C", "WO-B", "WO-A"]`.

### ISM-US-07 — batches: five newest by batch date, then batch id high to low
- **Rules:** `_usage` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B1 = batch("B-1", D(3)); pbl(B1, "input").
2. B2 = batch("B-2", D(1)); pbl(B2, "input").
3. B3 = batch("B-3", D(1)); pbl(B3, "input").
4. B4 = batch("B-4", D(5)); pbl(B4, "input").
5. B5 = batch("B-5", D(2)); pbl(B5, "input").
6. B6 = batch("B-6", D(4)); pbl(B6, "input").

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[b.batch_number for b in ud.batches] == ["B-3", "B-2", "B-5", "B-1", "B-6"]`.
2. returns: `uc.batch_line_count == 6`.

### ISM-US-08 — formulas: by name, then role, five at most
- **Rules:** `_usage` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FMD = pf("FM-4", "Delta"); pfl(FMD, "input").
2. FA = pf("FM-1", "Alpha"); pfl(FA, "output"); pfl(FA, "input").
3. FE = pf("FM-5", "Echo"); pfl(FE, "input").
4. FB = pf("FM-2", "Bravo"); pfl(FB, "input").
5. FF = pf("FM-6", "Foxtrot"); pfl(FF, "input").
6. FC = pf("FM-3", "Charlie"); pfl(FC, "input").

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(f.name, f.item_role) for f in ud.formulas] == [("Alpha", "input"), ("Alpha", "output"), ("Bravo", "input"), ("Charlie", "input"), ("Delta", "input")]`.

### ISM-US-09 — projects: by project name, then component name, five at most
- **Rules:** `_usage` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PB = proj("Bravo"); CBD = comp(PB, "Deck"); pcl(CBD); CBA = comp(PB, "Arch"); pcl(CBA).
2. PA = proj("Alpha"); CAW = comp(PA, "Wall"); pcl(CAW).
3. PC = proj("Charlie"); CCR = comp(PC, "Roof"); pcl(CCR); CCG = comp(PC, "Gate"); pcl(CCG); CCB = comp(PC, "Base"); pcl(CCB).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(p.project_name, p.component_name) for p in ud.projects] == [("Alpha", "Wall"), ("Bravo", "Arch"), ("Bravo", "Deck"), ("Charlie", "Base"), ("Charlie", "Gate")]`.
2. returns: `uc.project_component_count == 6`.

### ISM-US-10 — formula names sort case-insensitively
- **Rules:** `_usage` R4 [BUG-2522]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2522 (non-strict)
- **Fails today on:** Then 1 (today's order follows the database collation)

**Given**
1. FZ = pf("FM-1", "Zeta"); pfl(FZ, "input").
2. FA = pf("FM-2", "apex"); pfl(FA, "input").

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[f.name for f in ud.formulas] == ["apex", "Zeta"]`.

### ISM-US-11 — six formulas of one name: the five lowest formula ids are shown
- **Rules:** `_usage` R4 [BUG-2522]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2522 (non-strict)
- **Fails today on:** Then 1 (ties are undetermined, so any five may be shown)

**Given**
1. FK = `[pf(f"FM-{k}", "Mix") for k in range(1, 7)]`, each with one pfl(FK[k], "input"), built in that order.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[f.formula_id for f in ud.formulas] == [FK[0].id, FK[1].id, FK[2].id, FK[3].id, FK[4].id]`.

### ISM-US-12 — the formula preview orders by the formula id after name and role
- **Rules:** `_usage` R4 [BUG-2522] (HR-6 line)
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 2 (the preview's ORDER BY ends at the name and role)

**Given**
1. PF = pf("FM-1", "Mix"); pfl(PF, "input").
2. recorder.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[f.formula_id for f in ud.formulas] == [PF.id]`.
2. statement: in the recorded SELECT reading `production_formula_items` with `LIMIT`, the text after `ORDER BY` names the formula's `id` column.

### ISM-US-13 — project names sort case-insensitively
- **Rules:** `_usage` R4 [BUG-2522]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2522 (non-strict)
- **Fails today on:** Then 1 (today's order follows the database collation)

**Given**
1. PZ = proj("Zeta"); CZ = comp(PZ, "Deck"); pcl(CZ).
2. PA = proj("apex"); CA = comp(PA, "Deck"); pcl(CA).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.project_name for p in ud.projects] == ["apex", "Zeta"]`.

### ISM-US-14 — the project preview orders by the component id after the names
- **Rules:** `_usage` R4 [BUG-2522] (HR-6 line)
- **Kind:** bug
- **Expect:** xfail BUG-2522
- **Fails today on:** Then 2 (the preview's ORDER BY ends at the names)

**Given**
1. P = proj("Bridge"); C = comp(P, "Deck"); pcl(C).
2. recorder.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.component_id for p in ud.projects] == [C.id]`.
2. statement: in the recorded SELECT reading `project_component_items` with `LIMIT`, the text after `ORDER BY` names the component's `id` column.

### ISM-US-15 — a deleted work-order line neither counts nor shows
- **Rules:** `_usage` R2, R5 [BUG-2525]
- **Kind:** bug
- **Expect:** xfail BUG-2525
- **Fails today on:** Then 1 (the deleted line is counted: 2)

**Given**
1. O1 = wo("WO-1"); wol(O1) but deleted line.
2. O2 = wo("WO-2"); wol(O2).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.work_order_line_count == 1`.
2. returns: `[w.work_order_number for w in ud.work_orders] == ["WO-2"]`.

### ISM-US-16 — a line of a deleted work order neither counts nor shows
- **Rules:** `_usage` R2, R5 [BUG-2525]
- **Kind:** bug
- **Expect:** xfail BUG-2525
- **Fails today on:** Then 1 (the deleted order's line is counted: 2)

**Given**
1. OD = wo("WO-DEL") but deleted wo; wol(OD).
2. O2 = wo("WO-2"); wol(O2).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.work_order_line_count == 1`.
2. returns: `[w.work_order_number for w in ud.work_orders] == ["WO-2"]`.

### ISM-US-17 — a component of a deleted project neither counts nor shows
- **Rules:** `_usage` R2, R5 [BUG-2525]
- **Kind:** bug
- **Expect:** xfail BUG-2525
- **Fails today on:** Then 1 (the deleted project's component is counted: 2)

**Given**
1. PDL = proj("Old Bridge") but deleted proj; CD = comp(PDL, "Deck"); pcl(CD).
2. P = proj("Bridge"); C = comp(P, "Deck"); pcl(C).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.project_component_count == 1`.
2. returns: `[p.project_id for p in ud.projects] == [P.id]`.

### ISM-US-18 — two lines on one work order count as two lines
- **Rules:** `_usage` R1, R4a (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = wo("WO-1"); wol(O) but `created_at TS(1)`; wol(O) but `created_at TS(5)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.work_order_line_count == 2`.

### ISM-US-19 — a work order appears once, placed by its newest line
- **Rules:** `_usage` R4a [BUG-2526]
- **Kind:** bug
- **Expect:** xfail BUG-2526
- **Fails today on:** Then 1 (one entry per line: WO-1, WO-2, WO-1)

**Given**
1. O1 = wo("WO-1"); wol(O1) but `created_at TS(1)`; wol(O1) but `created_at TS(5)`.
2. O2 = wo("WO-2"); wol(O2) but `created_at TS(3)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[w.work_order_number for w in ud.work_orders] == ["WO-1", "WO-2"]`.

### ISM-US-20 — repeated lines do not take the five places
- **Rules:** `_usage` R4a [BUG-2526]
- **Kind:** bug
- **Expect:** xfail BUG-2526
- **Fails today on:** Then 1 (WO-1's five lines fill the preview)

**Given**
1. O1 = wo("WO-1"); five lines wol(O1) with `created_at` TS(6), TS(7), TS(8), TS(9), TS(10).
2. O2 = wo("WO-2"); wol(O2) but `created_at TS(2)`.
3. O3 = wo("WO-3"); wol(O3) but `created_at TS(1)`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[w.work_order_number for w in ud.work_orders] == ["WO-1", "WO-2", "WO-3"]`.

### ISM-US-21 — a component appears once
- **Rules:** `_usage` R4a [BUG-2526]
- **Kind:** bug
- **Expect:** xfail BUG-2526
- **Fails today on:** Then 1 (one entry per line: Deck twice)

**Given**
1. P = proj("Bridge"); C = comp(P, "Deck"); pcl(C); pcl(C).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.component_id for p in ud.projects] == [C.id]`.
2. returns: `uc.project_component_count == 2`.

### ISM-US-22 — a formula appears once per role
- **Rules:** `_usage` R4a [BUG-2526]
- **Kind:** bug
- **Expect:** xfail BUG-2526
- **Fails today on:** Then 1 (three entries: input twice)

**Given**
1. PF = pf("FM-1", "Mix"); pfl(PF, "input"); pfl(PF, "input"); pfl(PF, "output").

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(f.formula_id, f.item_role) for f in ud.formulas] == [(PF.id, "input"), (PF.id, "output")]`.
2. returns: `uc.formula_count == 3`.

### ISM-US-23 — a batch appears once per role
- **Rules:** `_usage` R4a [BUG-2526]
- **Kind:** bug
- **Expect:** xfail BUG-2526
- **Fails today on:** Then 1 (two entries for one role)

**Given**
1. B = batch("B-1", TD); pbl(B, "input"); pbl(B, "input").

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(b.batch_id, b.item_role) for b in ud.batches] == [(B.id, "input")]`.
2. returns: `uc.batch_line_count == 2`.

### ISM-US-24 — a line on another workspace's formula neither counts nor shows
- **Rules:** `_usage` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (counted and listed with W0's formula)

**Given**
1. PF0 = W0 pf("FM-Z", "Zero Mix"); pfl(PF0, "input") but `workspace_id W1.id`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.formula_count == 0`.
2. returns: `ud.formulas == []`.

### ISM-US-25 — a line on another workspace's batch neither counts nor shows
- **Rules:** `_usage` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (counted and listed with W2's batch)

**Given**
1. B9 = W2 batch("B-N", TD); pbl(B9, "input") but `workspace_id W1.id`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.batch_line_count == 0`.
2. returns: `ud.batches == []`.

### ISM-US-26 — a line on another workspace's component neither counts nor shows
- **Rules:** `_usage` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (counted and listed with W0's component)

**Given**
1. P0 = W0 proj("Zero Bridge"); C0 = comp(P0, "Zero Deck"); pcl(C0) but `workspace_id W1.id`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.project_component_count == 0`.
2. returns: `ud.projects == []`.

### ISM-US-27 — a component of this workspace under another workspace's project neither counts nor shows
- **Rules:** `_usage` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (counted and listed with W2's project name)

**Given**
1. P9 = W2 proj("Far Bridge"); C = comp(P9, "Stray") but `workspace_id W1.id`; pcl(C).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.project_component_count == 0`.
2. returns: `ud.projects == []`.

### ISM-US-28 — a line on a later workspace's work order neither counts nor shows
- **Rules:** `_usage` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (counted and listed with W2's work order number)

**Given**
1. O9 = W2 wo("WO-N"); wol(O9) but `workspace_id W1.id`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.work_order_line_count == 0`.
2. returns: `ud.work_orders == []`.

### ISM-US-29 — a line on an earlier workspace's work order neither counts nor shows
- **Rules:** `_usage` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (counted and listed with W0's work order number)

**Given**
1. O0 = W0 wo("WO-Z"); wol(O0) but `workspace_id W1.id`.
2. O1 = wo("WO-1"); wol(O1).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.work_order_line_count == 1`.
2. returns: `[w.work_order_id for w in ud.work_orders] == [O1.id]`.

### ISM-US-30 — nothing used: zero counts, empty previews
- **Rules:** `_usage` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `uc.formula_count == 0`, `uc.batch_line_count == 0`, `uc.project_component_count == 0`, `uc.work_order_line_count == 0`.
2. returns: `ud.formulas == []`, `ud.batches == []`, `ud.projects == []`, `ud.work_orders == []`.

## `ItemSummaryService._resolve_order_link`

Cards OL-01 … OL-20 call `svc._resolve_order_link(db, order_type=…, order_id=…, source_type=…, source_id=…)` (today's signature); OL-21 … OL-30 add the fix's required `workspace_id=W1.id` (R5, spec G3). R5 is also tested through `_recent_activity` (RA-19).

### ISM-OL-01 — a given type and id are returned as they are
- **Rules:** `_resolve_order_link` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so("SO-1", TD).

**When**
- `result = svc._resolve_order_link(db, order_type="sales_order", order_id=S.id, source_type="purchase_order", source_id=5)`.

**Then**
1. returns: `result == ("sales_order", S.id)`.

### ISM-OL-02 — a type with order id 0 falls through to the source
- **Rules:** `_resolve_order_link` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", TD) but `id XID(1)`; L = pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")) but `id XID(2)`.

**When**
- `result = svc._resolve_order_link(db, order_type="work_order", order_id=0, source_type="purchase_order", source_id=L.id)`.

**Then**
1. returns: `result == ("purchase_order", P.id)`.

### ISM-OL-03 — an order id with no type falls through to the source
- **Rules:** `_resolve_order_link` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", TD) but `id XID(1)`; L = pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")) but `id XID(2)`.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=77, source_type="purchase_order", source_id=L.id)`.

**Then**
1. returns: `result == ("purchase_order", P.id)`.

### ISM-OL-04 — no source type gives no link
- **Rules:** `_resolve_order_link` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type=None, source_id=5)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-05 — an empty source type gives no link
- **Rules:** `_resolve_order_link` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="", source_id=5)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-06 — source id 0 gives no link, nothing read
- **Rules:** `_resolve_order_link` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. recorder.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=0)`.

**Then**
1. returns: `result == (None, None)`.
2. statement: `len(stmts) == 0`.

### ISM-OL-07 — no source id gives no link
- **Rules:** `_resolve_order_link` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=None)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-08 — a purchase line source links to its order, not the line
- **Rules:** `_resolve_order_link` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", TD) but `id XID(1)`; L = pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")) but `id XID(2)`.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)`.

**Then**
1. returns: `result == ("purchase_order", XID(1))`.

### ISM-OL-09 — a transfer line source links to its order, not the line
- **Rules:** `_resolve_order_link` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = to("TO-1", NOON(TD)) but `id XID(1)`; TL = tol(T, Decimal("1.00")) but `id XID(2)`.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="transfer_order", source_id=TL.id)`.

**Then**
1. returns: `result == ("transfer_order", XID(1))`.

### ISM-OL-10 — a missing purchase line gives no link
- **Rules:** `_resolve_order_link` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order", source_id=MISSING)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-11 — a missing transfer line gives no link
- **Rules:** `_resolve_order_link` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="transfer_order", source_id=MISSING)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-12 — a manual source gives no link
- **Rules:** `_resolve_order_link` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="manual", source_id=5)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-13 — a production batch source gives no link
- **Rules:** `_resolve_order_link` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = batch("B-1", TD).

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="production_batch", source_id=B.id)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-14 — adjustment and reconciliation sources give no link
- **Rules:** `_resolve_order_link` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="adjustment", source_id=5)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-15 — a missing receive-event item gives no link
- **Rules:** `_resolve_order_link` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="po_receive_event_item", source_id=MISSING)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-16 — a receive-event item links to the purchase order
- **Rules:** `_resolve_order_link` R4a [BUG-2527]
- **Kind:** bug
- **Expect:** xfail BUG-2527
- **Fails today on:** Then 1 (today `(None, None)`)

**Given**
1. P = po("PO-1", TD) but `id XID(1)`; L = pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")).
2. E = rev(P); EI = revi(E, L).

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="po_receive_event_item", source_id=EI.id)`.

**Then**
1. returns: `result == ("purchase_order", XID(1))`.

### ISM-OL-17 — a receive-event item reversal links to the purchase order
- **Rules:** `_resolve_order_link` R4a [BUG-2527]
- **Kind:** bug
- **Expect:** xfail BUG-2527
- **Fails today on:** Then 1 (today `(None, None)`)

**Given**
1. P = po("PO-1", TD) but `id XID(1)`; L = pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")).
2. E = rev(P); EI = revi(E, L).

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="po_receive_event_item_reversal", source_id=EI.id)`.

**Then**
1. returns: `result == ("purchase_order", XID(1))`.

### ISM-OL-18 — a legacy purchase reversal links to the line's order
- **Rules:** `_resolve_order_link` R4a [BUG-2527]
- **Kind:** bug
- **Expect:** xfail BUG-2527
- **Fails today on:** Then 1 (today `(None, None)`)

**Given**
1. P = po("PO-1", TD) but `id XID(1)`; L = pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")) but `id XID(2)`.

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_order_reversal", source_id=L.id)`.

**Then**
1. returns: `result == ("purchase_order", XID(1))`.

### ISM-OL-19 — a purchase return item links to the return's purchase order
- **Rules:** `_resolve_order_link` R4a [BUG-2527]
- **Kind:** bug
- **Expect:** xfail BUG-2527
- **Fails today on:** Then 1 (today `(None, None)`)

**Given**
1. P = po("PO-1", TD) but `id XID(1)`; L = pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")).
2. R = ret(P, "RET-1"); RI = reti(R, L).

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="purchase_return_item", source_id=RI.id)`.

**Then**
1. returns: `result == ("purchase_order", XID(1))`.

### ISM-OL-20 — a work order source links to that work order
- **Rules:** `_resolve_order_link` R4a [BUG-2527]
- **Kind:** bug
- **Expect:** xfail BUG-2527
- **Fails today on:** Then 1 (today `(None, None)`)

**Given**
1. O = wo("WO-1").

**When**
- `result = svc._resolve_order_link(db, order_type=None, order_id=None, source_type="work_order", source_id=O.id)`.

**Then**
1. returns: `result == ("work_order", O.id)`.

### ISM-OL-21 — with the workspace given, a W1 purchase line resolves
- **Rules:** `_resolve_order_link` R3, R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P = po("PO-1", TD); L = pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)`.

**Then**
1. returns: `result == ("purchase_order", P.id)`.

### ISM-OL-22 — a purchase line of W2 gives no link
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P9 = W2 po("PO-N", TD); L9 = pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L9.id)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-23 — a purchase line of W0 gives no link
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P0 = W0 po("PO-Z", TD); L0 = pol(P0, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L0.id)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-24 — a transfer line of W2 gives no link
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. T9 = W2 to("TO-N", NOON(TD)) but `source_location_id F9.id`, `destination_location_id F9.id`; TL9 = tol(T9, Decimal("1.00")).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type=None, order_id=None, source_type="transfer_order", source_id=TL9.id)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-25 — a transfer line of W0 gives no link
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. T0X = W0 to("TO-Z", NOON(TD)) but `source_location_id F0.id`, `destination_location_id F0.id`; TL0 = tol(T0X, Decimal("1.00")).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type=None, order_id=None, source_type="transfer_order", source_id=TL0.id)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-26 — a W1 line on a W2 purchase order gives no link
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P9 = W2 po("PO-N", TD); L = pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")) but `workspace_id W1.id`.

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-27 — a given W1 order passes through with the workspace given
- **Rules:** `_resolve_order_link` R1, R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. S = so("SO-1", TD).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type="sales_order", order_id=S.id, source_type=None, source_id=None)`.

**Then**
1. returns: `result == ("sales_order", S.id)`.

### ISM-OL-28 — a given W2 order does not pass through
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. S9 = W2 so("SO-N", TD).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type="sales_order", order_id=S9.id, source_type=None, source_id=None)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-29 — a given W0 order does not pass through
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. S0 = W0 so("SO-Z", TD).

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type="sales_order", order_id=S0.id, source_type=None, source_id=None)`.

**Then**
1. returns: `result == (None, None)`.

### ISM-OL-30 — a given order id that does not exist does not pass through
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_link(db, workspace_id=W1.id, order_type="sales_order", order_id=MISSING, source_type=None, source_id=None)`.

**Then**
1. returns: `result == (None, None)`.

## `ItemSummaryService._resolve_order_number`

Cards ON-01 … ON-09 call `svc._resolve_order_number(db, order_type=…, order_id=…)` (today's signature); ON-10 … ON-14 add the fix's required `workspace_id=W1.id` (R3, spec G3). R3 is also tested through `_recent_activity` (RA-20).

### ISM-ON-01 — no type gives no number
- **Rules:** `_resolve_order_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", TD).

**When**
- `result = svc._resolve_order_number(db, order_type=None, order_id=P.id)`.

**Then**
1. returns: `result is None`.

### ISM-ON-02 — no id gives no number
- **Rules:** `_resolve_order_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_number(db, order_type="purchase_order", order_id=None)`.

**Then**
1. returns: `result is None`.

### ISM-ON-03 — a purchase order gives its PO number
- **Rules:** `_resolve_order_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", TD).

**When**
- `result = svc._resolve_order_number(db, order_type="purchase_order", order_id=P.id)`.

**Then**
1. returns: `result == "PO-1"`.

### ISM-ON-04 — a transfer order gives its transfer number
- **Rules:** `_resolve_order_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = to("TO-1", NOON(TD)).

**When**
- `result = svc._resolve_order_number(db, order_type="transfer_order", order_id=T.id)`.

**Then**
1. returns: `result == GN("TO-1")`.

### ISM-ON-05 — a sales order gives its sales order number
- **Rules:** `_resolve_order_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so("SO-1", TD) (no lines).

**When**
- `result = svc._resolve_order_number(db, order_type="sales_order", order_id=S.id)`.

**Then**
1. returns: `result == GN("SO-1")`.

### ISM-ON-06 — an expense order gives its expense number
- **Rules:** `_resolve_order_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = eo("EX-1").

**When**
- `result = svc._resolve_order_number(db, order_type="expense_order", order_id=X.id)`.

**Then**
1. returns: `result == "EX-1"`.

### ISM-ON-07 — a work order gives its work order number
- **Rules:** `_resolve_order_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = wo("WO-1").

**When**
- `result = svc._resolve_order_number(db, order_type="work_order", order_id=O.id)`.

**Then**
1. returns: `result == "WO-1"`.

### ISM-ON-08 — a missing order gives no number
- **Rules:** `_resolve_order_number` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._resolve_order_number(db, order_type="purchase_order", order_id=MISSING)`.

**Then**
1. returns: `result is None`.

### ISM-ON-09 — an unknown type gives no number
- **Rules:** `_resolve_order_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", TD).

**When**
- `result = svc._resolve_order_number(db, order_type="invoice", order_id=P.id)`.

**Then**
1. returns: `result is None`.

### ISM-ON-10 — with the workspace given, a W1 purchase order gives its number
- **Rules:** `_resolve_order_number` R2, R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P = po("PO-1", TD).

**When**
- `result = svc._resolve_order_number(db, workspace_id=W1.id, order_type="purchase_order", order_id=P.id)`.

**Then**
1. returns: `result == "PO-1"`.

### ISM-ON-11 — a W2 purchase order gives no number
- **Rules:** `_resolve_order_number` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P9 = W2 po("PO-N", TD).

**When**
- `result = svc._resolve_order_number(db, workspace_id=W1.id, order_type="purchase_order", order_id=P9.id)`.

**Then**
1. returns: `result is None`.

### ISM-ON-12 — a W0 purchase order gives no number
- **Rules:** `_resolve_order_number` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P0 = W0 po("PO-Z", TD).

**When**
- `result = svc._resolve_order_number(db, workspace_id=W1.id, order_type="purchase_order", order_id=P0.id)`.

**Then**
1. returns: `result is None`.

### ISM-ON-13 — a W2 work order gives no number
- **Rules:** `_resolve_order_number` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. O9 = W2 wo("WO-N").

**When**
- `result = svc._resolve_order_number(db, workspace_id=W1.id, order_type="work_order", order_id=O9.id)`.

**Then**
1. returns: `result is None`.

### ISM-ON-14 — a W0 sales order gives no number
- **Rules:** `_resolve_order_number` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. S0 = W0 so("SO-Z", TD).

**When**
- `result = svc._resolve_order_number(db, workspace_id=W1.id, order_type="sales_order", order_id=S0.id)`.

**Then**
1. returns: `result is None`.

## `ItemSummaryService._activity_from_ledger`

### ISM-AL-01 — the entry carries what it is given, with the resolved link and number
- **Rules:** `_activity_from_ledger` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", TD); L = pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._activity_from_ledger(db, source="inventory", performed_at=TS(1), transaction_type="manual_add", quantity=3, factory_id=F1.id, factory_name="Factory One", machine_id=None, machine_name=None, inventory_type="STORAGE", order_type=None, order_id=None, source_type="purchase_order", source_id=L.id)`.

**Then**
1. returns: `result.source == "inventory"`, `result.performed_at == TS(1)`, `result.transaction_type == "manual_add"`, `result.quantity == 3`.
2. returns: `result.factory_id == F1.id`, `result.factory_name == "Factory One"`, `result.machine_id is None`, `result.machine_name is None`, `result.inventory_type == "STORAGE"`.
3. returns: `result.order_type == "purchase_order"`, `result.order_id == P.id`.
4. returns: `result.order_number == "PO-1"`.

### ISM-AL-02 — no link gives no order fields
- **Rules:** `_activity_from_ledger` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._activity_from_ledger(db, source="machine", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=None, factory_name=None, machine_id=M1.id, machine_name="Press 1", inventory_type=None, order_type=None, order_id=None, source_type="manual", source_id=None)`.

**Then**
1. returns: `result.source == "machine"`, `result.machine_id == M1.id`, `result.machine_name == "Press 1"`.
2. returns: `result.order_type is None`, `result.order_id is None`, `result.order_number is None`.

### ISM-AL-03 — an unknown source raises a validation error
- **Rules:** `_activity_from_ledger` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `svc._activity_from_ledger(db, source="storage", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=F1.id, factory_name="Factory One", machine_id=None, machine_name=None, inventory_type="STORAGE", order_type=None, order_id=None, source_type=None, source_id=None)`.

**Then**
1. raises: `ValidationError`.

### ISM-AL-04 — the workspace is passed on: a W2 source line gives no order fields
- **Rules:** `_activity_from_ledger` R1, R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P9 = W2 po("PO-N", TD); L9 = pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._activity_from_ledger(db, workspace_id=W1.id, source="inventory", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=F1.id, factory_name="Factory One", source_type="purchase_order", source_id=L9.id)`.

**Then**
1. returns: `result.source == "inventory"`.
2. returns: `result.order_type is None`, `result.order_id is None`.
3. returns: `result.order_number is None`.

### ISM-AL-05 — the workspace is passed on: a W1 source line gives the link and number
- **Rules:** `_activity_from_ledger` R1, R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter today)

**Given**
1. P = po("PO-1", TD); L = pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).

**When**
- `result = svc._activity_from_ledger(db, workspace_id=W1.id, source="inventory", performed_at=TS(1), transaction_type="manual_add", quantity=1, factory_id=F1.id, factory_name="Factory One", source_type="purchase_order", source_id=L.id)`.

**Then**
1. returns: `result.order_type == "purchase_order"`, `result.order_id == P.id`.
2. returns: `result.order_number == "PO-1"`.

### ISM-AL-06 — the nine optional keywords default to None
- **Rules:** `_activity_from_ledger` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._activity_from_ledger(db, source="product", performed_at=TS(1), transaction_type="sale", quantity=1)`.

**Then**
1. returns: `result.source == "product"`, `result.quantity == 1`.
2. returns: `result.factory_id is None`, `result.factory_name is None`, `result.machine_id is None`, `result.machine_name is None`, `result.inventory_type is None`.
3. returns: `result.order_type is None`, `result.order_id is None`, `result.order_number is None`.

### ISM-AL-07 — arguments after db cannot be passed by position
- **Rules:** `_activity_from_ledger` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `svc._activity_from_ledger(db, "product", TS(1), "sale", 1)`.

**Then**
1. raises: `TypeError`.

## `ItemSummaryService._recent_activity`

Unless the card says otherwise, the When is `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)` (default `limit`).

### ISM-RA-01 — an inventory entry: source, time, factory, type text, int quantity
- **Rules:** `_recent_activity` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. ient(F1, TS(1)) but `inventory_type DAMAGED`, `quantity 3`, `qty_after 3`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].source == "inventory"`, `result[0].performed_at == TS(1)`, `result[0].transaction_type == "manual_add"`.
3. returns: `result[0].factory_id == F1.id`, `result[0].factory_name == "Factory One"`, `result[0].inventory_type == "DAMAGED"`.
4. returns: `result[0].quantity == 3`, `isinstance(result[0].quantity, int)`.
5. returns: `result[0].machine_id is None`, `result[0].order_type is None`.

### ISM-RA-02 — an inventory entry's purchase-line source gives the order link and number
- **Rules:** `_recent_activity` R2; `_activity_from_ledger` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", TD); L = pol(P, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. ient(F1, TS(1)) but `source_type "purchase_order"`, `source_id L.id`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `result[0].order_type == "purchase_order"`, `result[0].order_id == P.id`.
2. returns: `result[0].order_number == "PO-1"`.

### ISM-RA-03 — a factory missing from the map gives no factory name
- **Rules:** `_recent_activity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. ient(F2, TS(1)).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names={F1.id: "Factory One"}, machine_names=MMAP)`.

**Then**
1. returns: `result[0].factory_id == F2.id`.
2. returns: `result[0].factory_name is None`.

### ISM-RA-04 — a product entry: source product, factory, no inventory type
- **Rules:** `_recent_activity` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. pent(F1, TS(1)).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].source == "product"`, `result[0].factory_id == F1.id`, `result[0].factory_name == "Factory One"`.
3. returns: `result[0].inventory_type is None`, `result[0].quantity == 1`.

### ISM-RA-05 — a machine entry: machine name, and its own order type and id
- **Rules:** `_recent_activity` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = wo("WO-1").
2. ment(M1, TS(1)) but `order_type "work_order"`, `order_id O.id`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `result[0].source == "machine"`, `result[0].machine_id == M1.id`, `result[0].machine_name == "Press 1"`.
2. returns: `result[0].order_type == "work_order"`, `result[0].order_id == O.id`.
3. returns: `result[0].order_number == "WO-1"`.

### ISM-RA-06 — a machine entry with no order falls back to its source
- **Rules:** `_recent_activity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = to("TO-1", NOON(TD)); TL = tol(T, Decimal("1.00")).
2. ment(M1, TS(1)) but `source_type "transfer_order"`, `source_id TL.id`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `result[0].order_type == "transfer_order"`, `result[0].order_id == T.id`.
2. returns: `result[0].order_number == GN("TO-1")`.

### ISM-RA-07 — a machine missing from the map gives no machine name
- **Rules:** `_recent_activity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M2 = mach("Press 2").
2. ment(M2, TS(1)).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `result[0].machine_id == M2.id`.
2. returns: `result[0].machine_name is None`.

### ISM-RA-08 — the three ledgers merge newest first
- **Rules:** `_recent_activity` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. ment(M1, TS(2)).
2. ient(F1, TS(4)).
3. pent(F1, TS(3)).
4. ient(F1, TS(1)).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[(a.source, a.performed_at) for a in result] == [("inventory", TS(4)), ("product", TS(3)), ("machine", TS(2)), ("inventory", TS(1))]`.

### ISM-RA-09 — the default limit is 10 across the three ledgers
- **Rules:** `_recent_activity` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. ient(F1, TS(k)) for k in 1, 3, 5, 7.
2. pent(F1, TS(k)) for k in 2, 4, 6, 8.
3. ment(M1, TS(k)) for k in 9, 10, 11, 12.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[a.performed_at for a in result] == [TS(k) for k in range(12, 2, -1)]`.

### ISM-RA-10 — a limit above 5 returns that many newest entries
- **Rules:** `_recent_activity` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. ient(F1, TS(k)) for k in 1 … 7, built in the order 4, 1, 7, 2, 6, 3, 5.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP, limit=6)`.

**Then**
1. returns: `[a.performed_at for a in result] == [TS(7), TS(6), TS(5), TS(4), TS(3), TS(2)]`.

### ISM-RA-11 — a limit below 5 still reads 5 entries per ledger
- **Rules:** `_recent_activity` R1
- **Kind:** boundary
- **Author:** claude
- **Expect:** pass

**Given**
1. ient(F1, TS(k)) for k in 1 … 6.
2. recorder.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP, limit=1)`.

**Then**
1. returns: `[a.performed_at for a in result] == [TS(6)]`.
2. statement: the recorded SELECT reading `inventory_ledger` carries a row limit of 5 (the `LIMIT` value, in the text or its parameters).

### ISM-RA-12 — equal times keep the order inventory, product, machine
- **Rules:** `_recent_activity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. ment(M1, TS(5)).
2. pent(F1, TS(5)).
3. ient(F1, TS(5)).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[a.source for a in result] == ["inventory", "product", "machine"]`.

### ISM-RA-13 — entries of a deleted factory and a deleted machine are history and stay
- **Rules:** `_recent_activity` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = mach("Press 4") but deleted machine.
2. ient(FD, TS(1)).
3. ment(MD, TS(2)).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names={M1.id: "Press 1", MD.id: "Press 4"})`.

**Then**
1. returns: `[(a.source, a.factory_name, a.machine_name) for a in result] == [("machine", None, "Press 4"), ("inventory", "Old Plant", None)]`.

### ISM-RA-14 — a removed item's entries stay
- **Rules:** `_recent_activity` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. ient(F1, TS(1)) but `item_id IR.id`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=IR.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[a.performed_at for a in result] == [TS(1)]`.

### ISM-RA-15 — no entries gives an empty list
- **Rules:** `_recent_activity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `result == []`.

### ISM-RA-16 — only this workspace's entries of this item
- **Rules:** `_recent_activity` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. W0 ient(F0, TS(5)) but `item_id I0.id`.
2. W0 pent(F0, TS(6)).
3. ient(F1, TS(1)).
4. ient(F1, TS(7)) but `item_id I2.id`.
5. W2 ient(F9, TS(8)).
6. W2 ment(M9, TS(9)) but `item_id I9.id`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[(a.source, a.performed_at) for a in result] == [("inventory", TS(1))]`.

### ISM-RA-17 — an entry in another workspace's factory shows no factory
- **Rules:** `_recent_activity` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 2 (`factory_id` is W2's factory id)

**Given**
1. ient(F9, TS(1)) (a W1 entry pointing at W2's factory).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].factory_id is None`.
3. returns: `result[0].factory_name is None`.

### ISM-RA-18 — an entry on another workspace's machine shows no machine
- **Rules:** `_recent_activity` R6 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 2 (`machine_id` is W0's machine id)

**Given**
1. ment(M0, TS(1)) (a W1 entry pointing at W0's machine).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].machine_id is None`.
3. returns: `result[0].machine_name is None`.

### ISM-RA-19 — a source line of another workspace gives no link
- **Rules:** `_resolve_order_link` R5 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 2 (linked to W2's purchase order)

**Given**
1. P9 = W2 po("PO-N", TD); L9 = pol(P9, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. ient(F1, TS(1)) but `source_type "purchase_order"`, `source_id L9.id`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].order_type is None`, `result[0].order_id is None`.
3. returns: `result[0].order_number is None`.

### ISM-RA-20 — another workspace's order named on a machine entry gives no link or number
- **Rules:** `_resolve_order_number` R3 [BUG-2520]
- **Kind:** bug
- **Expect:** xfail BUG-2520
- **Fails today on:** Then 2 (W0's PO number is shown)

**Given**
1. P0 = W0 po("PO-Z", TD).
2. ment(M1, TS(1)) but `order_type "purchase_order"`, `order_id P0.id`.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].order_number is None`.
3. returns: `result[0].order_type is None`, `result[0].order_id is None`.

### ISM-RA-21 — links are read together, only for the returned entries
- **Rules:** `_recent_activity` R7 [BUG-2528]
- **Kind:** bug
- **Expect:** xfail BUG-2528
- **Fails today on:** Then 3 (one purchase-line read per entry)

**Given**
1. For k in 1 … 12: Pk = po(f"PO-{k}", TD); Lk = pol(Pk, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")); ient(F1, TS(k)) but `source_type "purchase_order"`, `source_id Lk.id`.
2. recorder.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[a.order_number for a in result] == [f"PO-{k}" for k in range(12, 2, -1)]`.
2. returns: `len(result) == 10`.
3. statement: at most 1 recorded SELECT reads `purchase_order_items`.
4. statement: at most 1 recorded SELECT reads `FROM purchase_orders`.

### ISM-RA-22 — an inventory entry with no time gets naive UTC now, not the database's local time
- **Rules:** `_recent_activity` R3 [BUG-2529]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2529
- **Fails today on:** Then 2 (under `Asia/Dhaka` the stored time is 6 hours ahead of UTC)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`.
2. ient(F1, TS(1)) but `performed_at` not passed (the column default fills it).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `abs(datetime.now(timezone.utc).replace(tzinfo=None) - result[0].performed_at.replace(tzinfo=None)) < timedelta(minutes=5)`.

### ISM-RA-23 — a zone-aware machine time merges with a naive one by its UTC instant
- **Rules:** `_recent_activity` R3, R3a [BUG-2487]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2487
- **Fails today on:** Then 1 (the call raises TypeError: a naive and an aware datetime are compared in the sort)

**Given**
1. ient(F1, TS(1)) (naive `datetime(2026, 1, 2, 12, 0)`).
2. ME = ment(M1, AWARE) where AWARE = `datetime(2026, 1, 2, 15, 0, tzinfo=timezone(timedelta(hours=6)))` (09:00 UTC); flushed, then neither expired nor refreshed, so the session's object keeps the aware value.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[a.source for a in result] == ["inventory", "machine"]`.
2. returns: `result[0].performed_at == datetime(2026, 1, 2, 12, 0)`.
3. returns: `result[1].performed_at == datetime(2026, 1, 2, 9, 0)`.
4. returns: `result[1].performed_at.tzinfo is None`.

### ISM-RA-24 — a lone zone-aware time comes back as naive UTC
- **Rules:** `_recent_activity` R3a [BUG-2487]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-2487
- **Fails today on:** Then 2 (today the aware value is returned as it is: 15:00+06:00)

**Given**
1. ME = ment(M1, AWARE) where AWARE = `datetime(2026, 1, 2, 15, 0, tzinfo=timezone(timedelta(hours=6)))`; flushed, then neither expired nor refreshed.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].performed_at.tzinfo is None`.
3. returns: `result[0].performed_at == datetime(2026, 1, 2, 9, 0)`.

## DAO bugs reached through the summary (one pass-through card each)

### ISM-DP-01 — stock in a soft-deleted factory is not listed or totalled
- **Rules:** `_inventory_rows` R1 [BUG-884]
- **Kind:** bug
- **Expect:** xfail BUG-884
- **Fails today on:** Then 1 (the deleted factory's stock is listed)

**Given**
1. stock(FD, STORAGE, 4, Decimal("1.00")).
2. stock(F1, STORAGE, 5, Decimal("1.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.inventory_rows] == [F1.id]`.
2. returns: `result.kpis.storage_qty_total == 5`.

### ISM-DP-02 — finished goods of a deleted factory are not listed
- **Rules:** `_product_rows` R1 [BUG-1328]
- **Kind:** bug
- **Expect:** xfail BUG-1328
- **Fails today on:** Then 1 (the deleted factory's row is listed)

**Given**
1. prod(FD, 4, Decimal("1.00"), Decimal("2.00")).
2. prod(F1, 5, Decimal("1.00"), Decimal("2.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.factory_id for r in result.product_rows] == [F1.id]`.
2. returns: `result.kpis.product_qty_total == 5`.

### ISM-DP-03 — a removed item shows no finished goods
- **Rules:** `_product_rows` R1 [BUG-1338]; `get_summary` R7
- **Kind:** bug
- **Expect:** xfail BUG-1338
- **Fails today on:** Then 2 (the removed item's product row is listed)

**Given**
1. prod(F1, 5, Decimal("1.00"), Decimal("2.00")) but `item_id IR.id`.

**When**
- `result = svc.get_summary(db, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.item.id == IR.id`.
2. returns: `result.product_rows == []`.
3. returns: `result.kpis.product_qty_total == 0`.

### ISM-DP-04 — a placement on a deleted machine is not listed
- **Rules:** `_machine_placements` R1 [BUG-981]
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (shown as `Machine #<id>` and counted)

**Given**
1. MD = mach("Press 4") but deleted machine; place(MD, 3, None).
2. place(M1, 2, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_id for p in result.machine_placements] == [M1.id]`.
2. returns: `result.kpis.machine_placement_count == 1`.

### ISM-DP-05 — a placement on a machine of a deleted factory is not listed
- **Rules:** `_machine_placements` R1 [BUG-981]; `_machine_location_map` R5
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (shown with "Old Plant" and counted)

**Given**
1. MF = mach("Lost Press") but `factory_id FD.id`; place(MF, 3, None).
2. place(M1, 2, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[p.machine_id for p in result.machine_placements] == [M1.id]`.
2. returns: `result.kpis.machine_placement_count == 1`.

### ISM-DP-06 — placements are not capped at 500
- **Rules:** `_machine_placements` R1 [BUG-982]
- **Kind:** bug
- **Expect:** xfail BUG-982
- **Fails today on:** Then 1 (500 placements come back)

**Given**
1. For k in 1 … 501: Mk = mach(f"M{k:03d}"); place(Mk, 1, None).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.machine_placements) == 501`.
2. returns: `result.kpis.machine_placement_count == 501`.

### ISM-DP-07 — the placement read has an ORDER BY
- **Rules:** `_machine_placements` R5 [BUG-977]
- **Kind:** bug
- **Expect:** xfail BUG-977
- **Fails today on:** Then 2 (the `machine_items` read has no ORDER BY)

**Given**
1. place(M1, 2, None).
2. recorder.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.machine_placements) == 1`.
2. statement: the recorded SELECT reading `machine_items` contains `ORDER BY`.

### ISM-DP-08 — the finished-goods read has an ORDER BY
- **Rules:** `_product_rows` R5 [BUG-1326]
- **Kind:** bug
- **Expect:** xfail BUG-1326
- **Fails today on:** Then 2 (the `products` read has no ORDER BY)

**Given**
1. prod(F1, 5, Decimal("1.00"), Decimal("2.00")).
2. recorder.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.product_rows) == 1`.
2. statement: the recorded SELECT reading `FROM products` contains `ORDER BY`.

### ISM-DP-09 — the item's tag read has an ORDER BY
- **Rules:** `get_summary` R3 [BUG-932]
- **Kind:** bug
- **Expect:** xfail BUG-932
- **Fails today on:** Then 2 (the tag read has no ORDER BY)

**Given**
1. TR = tag("Red", "red"); tagged(I1, TR).
2. recorder.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t in result.item.tags] == [TR.id]`.
2. statement: the recorded SELECT reading `item_tag_assignments` contains `ORDER BY`.

### ISM-DP-10 — the product ledger read breaks time ties by id
- **Rules:** `_recent_activity` R1 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 2 (ORDER BY names `performed_at` only)

**Given**
1. pent(F1, TS(1)).
2. recorder.

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `[a.source for a in result] == ["product"]`.
2. statement: in the recorded SELECT reading `product_ledger`, the text after `ORDER BY` names `product_ledger.id`.

### ISM-DP-11 — a product entry with no time gets naive UTC now
- **Rules:** `_recent_activity` R3 [BUG-1337]
- **Kind:** bug
- **Author:** claude
- **Expect:** xfail BUG-1337
- **Fails today on:** Then 2 (under `Asia/Dhaka` the stored time is 6 hours ahead of UTC)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`.
2. pent(F1, TS(1)) but `performed_at` not passed (the column default fills it).

**When**
- `result = svc._recent_activity(db, workspace_id=W1.id, item_id=I1.id, factory_names=FMAP, machine_names=MMAP)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `abs(datetime.now(timezone.utc).replace(tzinfo=None) - result[0].performed_at.replace(tzinfo=None)) < timedelta(minutes=5)`.

## Owner answer — OQ-31 (BUG-2485)

Sales lines in the order statistics (`_order_stats_for_item` R5, R5a). The owner answered 2026-11-10: `total_spend` counts purchases only; sales line totals go into the new field `sales_revenue`; transfers add to no money figure. Each card calls `svc._order_stats_for_item(db, …)` or `get_summary` as written.

### ISM-OQ31-01 — a sales line's total goes to sales revenue, not to spend
- **Rules:** `_order_stats_for_item` R5, R5a [BUG-2485]
- **Kind:** bug
- **Expect:** xfail BUG-2485
- **Fails today on:** Then 4 (today `total_spend == Decimal("300.00")`)

**Given**
1. S = so("SO-1", D(5)); sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.sales_qty == Decimal("3.00")`.
2. returns: `result.total_quantity == Decimal("3.00")`.
3. returns: `result.line_count == 1`.
4. returns: `result.total_spend == Decimal("0")`.
5. returns: `result.sales_revenue == Decimal("300.00")`.
6. returns: `str(result.sales_revenue) == "300.00"`.

### ISM-OQ31-02 — total spend is purchase subtotals only, next to a sale and a transfer
- **Rules:** `_order_stats_for_item` R2, R4, R5, R5a [BUG-2485]
- **Kind:** bug
- **Expect:** xfail BUG-2485
- **Fails today on:** Then 3 (today `total_spend == Decimal("350.00")`)

**Given**
1. P = po("PO-1", D(5)); pol(P, Decimal("20.00"), Decimal("2.50"), Decimal("50.00")).
2. T = to("TO-1", NOON(D(5))); tol(T, Decimal("4.00")).
3. S = so("SO-1", D(5)); sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.total_quantity == Decimal("27.00")`.
2. returns: `result.line_count == 3`.
3. returns: `result.total_spend == Decimal("50.00")`.
4. returns: `str(result.total_spend) == "50.00"`.
5. returns: `result.sales_revenue == Decimal("300.00")`.

### ISM-OQ31-03 — sales revenue follows the window by order date, both ends in
- **Rules:** `_order_stats_for_item` R5, R5a [BUG-2485]
- **Kind:** bug
- **Expect:** xfail BUG-2485
- **Fails today on:** Then 2 (today `total_spend == Decimal("5.00")`)

**Given**
1. SA = so("SO-A", D(30)); sol(SA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. SB = so("SO-B", D(31)); sol(SB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).
3. SC = so("SO-C", TD); sol(SC, Decimal("4.00"), Decimal("1.00"), Decimal("4.00")).
4. SE = so("SO-E", D(-1)); sol(SE, Decimal("8.00"), Decimal("1.00"), Decimal("8.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=D(30), to_date=TD)`.

**Then**
1. returns: `result.sales_qty == Decimal("5.00")`.
2. returns: `result.total_spend == Decimal("0")`.
3. returns: `result.sales_revenue == Decimal("5.00")`.

### ISM-OQ31-04 — other workspaces' sales lines and other items add no revenue
- **Rules:** `_order_stats_for_item` R1, R5a [BUG-2485]
- **Kind:** bug
- **Expect:** xfail BUG-2485
- **Fails today on:** Then 3 (today `total_spend == Decimal("1.00")`)

**Given**
1. S0 = W0 so("SO-Z", D(5)); sol(S0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00")).
2. S1X = so("SO-1", D(5)); sol(S1X, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")); sol(S1X, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")) but `item_id I2.id`.
3. S9 = W2 so("SO-N", D(5)); sol(S9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.sales_qty == Decimal("1.00")`.
2. returns: `result.line_count == 1`.
3. returns: `result.total_spend == Decimal("0")`.
4. returns: `result.sales_revenue == Decimal("1.00")`.

### ISM-OQ31-05 — the summary's all-time total spend leaves sales out
- **Rules:** `_order_stats_for_item` R5a [BUG-2485]; `get_summary` R6
- **Kind:** bug
- **Expect:** xfail BUG-2485
- **Fails today on:** Then 2 (today `total_spend == Decimal("350.00")`)

**Given**
1. P = po("PO-1", G(5)); pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00")).
2. S = so("SO-1", G(5)); sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.order_stats.all_time.sales_qty == Decimal("3.00")`.
2. returns: `result.order_stats.all_time.total_spend == Decimal("50.00")`.
3. returns: `result.order_stats.all_time.sales_revenue == Decimal("300.00")`.

### ISM-OQ31-06 — purchase, transfer and sales quantities add up, one line each
- **Rules:** `_order_stats_for_item` R2, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", D(5)); pol(P, Decimal("20.00"), Decimal("2.50"), Decimal("50.00")).
2. T = to("TO-1", NOON(D(5))); tol(T, Decimal("4.00")).
3. S = so("SO-1", D(5)); sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.purchase_qty == Decimal("20.00")`.
2. returns: `result.transfer_qty == Decimal("4.00")`.
3. returns: `result.sales_qty == Decimal("3.00")`.
4. returns: `result.total_quantity == Decimal("27.00")`.
5. returns: `result.line_count == 3`.

### ISM-OQ31-07 — sales quantities are dated by order date, both window ends in
- **Rules:** `_order_stats_for_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SA = so("SO-A", D(30)); sol(SA, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")).
2. SB = so("SO-B", D(31)); sol(SB, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")).
3. SC = so("SO-C", TD); sol(SC, Decimal("4.00"), Decimal("1.00"), Decimal("4.00")).
4. SE = so("SO-E", D(-1)); sol(SE, Decimal("8.00"), Decimal("1.00"), Decimal("8.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=D(30), to_date=TD)`.

**Then**
1. returns: `result.sales_qty == Decimal("5.00")`.
2. returns: `result.line_count == 2`.

### ISM-OQ31-08 — other workspaces' sales lines and other items add no quantity
- **Rules:** `_order_stats_for_item` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = W0 so("SO-Z", D(5)); sol(S0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00")).
2. S1X = so("SO-1", D(5)); sol(S1X, Decimal("1.00"), Decimal("1.00"), Decimal("1.00")); sol(S1X, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")) but `item_id I2.id`.
3. S9 = W2 so("SO-N", D(5)); sol(S9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00")).

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.sales_qty == Decimal("1.00")`.
2. returns: `result.total_quantity == Decimal("1.00")`.
3. returns: `result.line_count == 1`.

### ISM-OQ31-09 — the summary's all-time stats count the sold quantity
- **Rules:** `_order_stats_for_item` R5; `get_summary` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", G(5)); pol(P, Decimal("10.00"), Decimal("5.00"), Decimal("50.00")).
2. S = so("SO-1", G(5)); sol(S, Decimal("3.00"), Decimal("100.00"), Decimal("300.00")).

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.order_stats.all_time.sales_qty == Decimal("3.00")`.
2. returns: `result.order_stats.all_time.total_quantity == Decimal("13.00")`.
3. returns: `result.order_stats.all_time.line_count == 2`.

### ISM-OQ31-10 — nothing matching gives zero sales revenue
- **Rules:** `_order_stats_for_item` Returns, R5a [BUG-2485]
- **Kind:** bug
- **Expect:** xfail BUG-2485
- **Fails today on:** Then 2 (the stats have no `sales_revenue` field: AttributeError)

**Given**
1. Standing rows only.

**When**
- `result = svc._order_stats_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result.total_spend == 0`.
2. returns: `result.sales_revenue == Decimal("0")`.

## Owner answer — OQ-32 (BUG-2486)

Open purchase lines (`_pricing` R4, R4b). The owner answered 2026-11-10: lines of an order in its workflow's last status are not open (and voided orders, BUG-2521, PRC-09). "Last" = the last id of the `status_sequence` of the order's workflow of the same workspace; no workflow or an empty sequence leaves the order open. Every card calls `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

### ISM-OQ32-01 — a partly received line is open for the rest
- **Rules:** `_pricing` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("6.00")`.

### ISM-OQ32-02 — a fully received line is not open; none open gives 0
- **Rules:** `_pricing` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("10.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 0`.
2. returns: `result.open_qty_outstanding == 0`.

### ISM-OQ32-03 — received plus refunded equal to ordered is not open
- **Rules:** `_pricing` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("6.00")`, `quantity_refunded Decimal("4.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 0`.
2. returns: `result.open_qty_outstanding == 0`.

### ISM-OQ32-04 — one hundredth short is open
- **Rules:** `_pricing` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("6.00")`, `quantity_refunded Decimal("3.99")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("0.01")`.

### ISM-OQ32-05 — an over-received line is not open
- **Rules:** `_pricing` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("12.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 0`.
2. returns: `result.open_qty_outstanding == 0`.

### ISM-OQ32-06 — a fully refunded line is not open
- **Rules:** `_pricing` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)); pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_refunded Decimal("10.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 0`.

### ISM-OQ32-07 — the outstanding quantity sums every open line
- **Rules:** `_pricing` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-1", D(3)).
2. pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.
3. pol(P, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")) but `quantity_refunded Decimal("1.00")`.
4. pol(P, Decimal("3.00"), Decimal("1.00"), Decimal("3.00")) but `quantity_received Decimal("3.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 2`.
2. returns: `result.open_qty_outstanding == Decimal("10.00")`.

### ISM-OQ32-08 — an order with no workflow stays open, whatever its status is called
- **Rules:** `_pricing` R4, R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. P = po("PO-1", D(3)) but `current_status_id SC.id`; pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")) but `quantity_received Decimal("70.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("30.00")`.

### ISM-OQ32-09 — open lines of other workspaces and other items do not count
- **Rules:** `_pricing` R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po("PO-Z", D(3)); pol(P0, Decimal("7.00"), Decimal("1.00"), Decimal("7.00")).
2. P1 = po("PO-1", D(3)); pol(P1, Decimal("2.00"), Decimal("1.00"), Decimal("2.00")); pol(P1, Decimal("5.00"), Decimal("1.00"), Decimal("5.00")) but `item_id I2.id`.
3. P9 = W2 po("PO-N", D(3)); pol(P9, Decimal("9.00"), Decimal("1.00"), Decimal("9.00")).

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("2.00")`.

### ISM-OQ32-10 — an order in its workflow's last status is not open
- **Rules:** `_pricing` R4b [BUG-2486]
- **Kind:** bug
- **Expect:** xfail BUG-2486
- **Fails today on:** Then 1 (today the line counts: 1)

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF = wf([S1.id, SC.id]).
3. P = po("PO-1", D(3)) but `current_status_id SC.id`, `order_workflow_id WF.id`; pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")) but `quantity_received Decimal("70.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 0`.
2. returns: `result.open_qty_outstanding == 0`.

### ISM-OQ32-11 — an order at an earlier status of its workflow stays open
- **Rules:** `_pricing` R4, R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF = wf([S1.id, SC.id]).
3. P = po("PO-1", D(3)) but `order_workflow_id WF.id`; pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")) but `quantity_received Decimal("70.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("30.00")`.

### ISM-OQ32-12 — "last" is the position in the sequence, not the status's name
- **Rules:** `_pricing` R4b [BUG-2486]
- **Kind:** bug
- **Expect:** xfail BUG-2486
- **Fails today on:** Then 1 (today the line counts: 1)

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF = wf([SC.id, S1.id]).
3. P = po("PO-1", D(3)) but `order_workflow_id WF.id`; pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 0`.
2. returns: `result.open_qty_outstanding == 0`.

### ISM-OQ32-13 — a workflow with an empty sequence leaves the order open
- **Rules:** `_pricing` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF = wf([]).
3. P = po("PO-1", D(3)) but `current_status_id SC.id`, `order_workflow_id WF.id`; pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("6.00")`.

### ISM-OQ32-14 — a W2 workflow does not close a W1 order
- **Rules:** `_pricing` R4b
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF9 = W2 wf([S1.id, SC.id]).
3. P = po("PO-1", D(3)) but `current_status_id SC.id`, `order_workflow_id WF9.id`; pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("6.00")`.

### ISM-OQ32-15 — a W0 workflow does not close a W1 order
- **Rules:** `_pricing` R4b
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF0 = W0 wf([S1.id, SC.id]).
3. P = po("PO-1", D(3)) but `current_status_id SC.id`, `order_workflow_id WF0.id`; pol(P, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("6.00")`.

### ISM-OQ32-16 — only the open order's lines are summed next to a closed one
- **Rules:** `_pricing` R4, R4b [BUG-2486]
- **Kind:** bug
- **Expect:** xfail BUG-2486
- **Fails today on:** Then 1 (today both lines count: 2)

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF = wf([S1.id, SC.id]).
3. PC = po("PO-C", D(3)) but `current_status_id SC.id`, `order_workflow_id WF.id`; pol(PC, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")) but `quantity_received Decimal("70.00")`.
4. PO = po("PO-O", D(3)) but `order_workflow_id WF.id`; pol(PO, Decimal("10.00"), Decimal("1.00"), Decimal("10.00")) but `quantity_received Decimal("4.00")`.

**When**
- `result = svc._pricing(db, workspace_id=W1.id, item_id=I1.id, today=TD)`.

**Then**
1. returns: `result.open_po_line_count == 1`.
2. returns: `result.open_qty_outstanding == Decimal("6.00")`.

### ISM-OQ32-17 — the summary shows no open line for a closed order
- **Rules:** `_pricing` R4b [BUG-2486]; `get_summary` R6
- **Kind:** bug
- **Expect:** xfail BUG-2486
- **Fails today on:** Then 1 (today 1)

**Given**
1. SC = `Status(workspace_id=W1.id, name="Completed", comment="Final")`.
2. WF = wf([S1.id, SC.id]).
3. P = po("PO-1", G(3)) but `current_status_id SC.id`, `order_workflow_id WF.id`; pol(P, Decimal("100.00"), Decimal("1.00"), Decimal("100.00")) but `quantity_received Decimal("70.00")`.

**When**
- `result = svc.get_summary(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.pricing.open_po_line_count == 0`.
2. returns: `result.pricing.open_qty_outstanding == 0`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_summary` R2 / FU-1 (BUG-937) | `ItemManager.get_item`, `ItemService` (`tests/unit/managers/item_manager.spec.md`) | when `include_deleted` is added, the summary passes `include_deleted=True`; GS-04 then keeps passing unchanged |
| Overview "Integration-only" | `app/core/exceptions.py` spec | the RFC 7807 body of the 404 |
| Overview "Integration-only" | `GET /items/{item_id}/summary/` | the caller's workspace comes from `get_current_workspace` |

## Spec gaps
None. G1–G9 of revision 1 are closed in the spec's round 2 (Gap log, 2026-11-10) and applied here (see Revision 2).

## Retired IDs
- ISM-OQ31-11 — `sales_order_items.unit_price` and `line_total` are NOT NULL, so a sales line with no total cannot be stored; R5a's "empty total counts as 0" part is unreachable for sales lines (revision 3).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_dec` | R1 | DEC-01 |
| `_dec` | R2 | DEC-02, DEC-03, DEC-04, DEC-05 |
| `_dec` | R3 / Errors | DEC-06 |
| `_est_value` | R1 | EST-01 |
| `_est_value` | R2 | EST-02, EST-03, EST-04 |
| `_est_value` | R3 | EST-04, EST-05, EST-06, EST-07 |
| `get_summary` | R1 / Errors row 1 | GS-01, GS-02, GS-03 |
| `get_summary` | R2 | GS-04, GS-07 |
| `get_summary` | R3 | GS-05, GS-06, GS-07; BUG-932 DP-09 |
| `get_summary` | R4 | GS-08, IV-02, MP-03 |
| `get_summary` | R5 | GS-09, GS-10 |
| `get_summary` | R6 | GS-08 … GS-11, GS-13, IV-01, OQ31-05, every US card |
| `get_summary` | R7 [BUG-1339] | GS-12 (xfail), GS-13 (pass part), DP-03 |
| `get_summary` | R8 | GS-14, GS-15 |
| `_factory_name_map` | R1 | FN-01, FN-02 |
| `_machine_name_map` | R1 | MN-01 |
| `_machine_location_map` | R1 | ML-01, ML-02, ML-03 |
| `_machine_location_map` | R2 | ML-02 |
| `_machine_location_map` | R3 [BUG-2520] | ML-05, ML-06, ML-07 |
| `_machine_location_map` | R4 [BUG-2525] | ML-08 |
| `_machine_location_map` | R5 | ML-04, DP-05 |
| `_inventory_rows` | R1 [BUG-884] | IV-04, IV-05, IV-06, GS-11; DP-01 |
| `_inventory_rows` | R2 | IV-01, IV-07, IV-08 |
| `_inventory_rows` | R3 | IV-02 |
| `_inventory_rows` | R4 | IV-02, IV-03 |
| `_inventory_rows` | R5 | IV-02, IV-03, IV-04 |
| `_inventory_rows` | R6 [BUG-2520] | IV-12, IV-13 |
| `_inventory_rows` | R7 [BUG-2522] | IV-09; IV-10, IV-11 |
| `_inventory_rows` | R8 [BUG-1339] | GS-12 |
| `_product_rows` | R1 [BUG-1328, BUG-1338] | PD-05, PD-06, PD-07; DP-02, DP-03 |
| `_product_rows` | R2 | PD-01, PD-02, PD-03, PD-04, PD-08, PD-14 |
| `_product_rows` | R3 | PD-01, PD-05, PD-06 |
| `_product_rows` | R4 [BUG-2520] | PD-12, PD-13 |
| `_product_rows` | R5 [BUG-2522, BUG-1326] | PD-09; PD-10, PD-11; DP-08 |
| `_machine_placements` | R1 [BUG-981, BUG-982] | MP-01, MP-03, MP-04; DP-04, DP-05, DP-06 |
| `_machine_placements` | R2 | MP-01, MP-02 |
| `_machine_placements` | R3 [BUG-2520] | MP-10, MP-11 (the `Machine #id` / `—` fallback exists only on bug paths today and gets no pass card) |
| `_machine_placements` | R4 [BUG-1339] | GS-12 |
| `_machine_placements` | R5 [BUG-2522, BUG-977] | MP-05; MP-06, MP-07, MP-08, MP-09; DP-07 |
| `_order_stats_for_item` | R1 | OS-10, GS-11, OQ31-04 |
| `_order_stats_for_item` | R2 | OS-01, OS-02, OS-13, OQ31-02 |
| `_order_stats_for_item` | R2a [BUG-2521] | OS-12 |
| `_order_stats_for_item` | R3 | OS-03, OS-04, OS-05, GS-09 |
| `_order_stats_for_item` | R4 | OS-08, OS-09 |
| `_order_stats_for_item` | R5 | OQ31-06, OQ31-07, OQ31-08, OQ31-09; OQ31-01 … OQ31-04 (xfail) |
| `_order_stats_for_item` | R5a [BUG-2485] | OQ31-01 … OQ31-05, OQ31-10 (the "empty total counts as 0" part is unreachable for sales lines: NOT NULL; OQ31-11 retired) |
| `_order_stats_for_item` | R6 | OS-06, OS-07 |
| `_order_stats_for_item` | R7 | OS-08 |
| `_order_stats_for_item` | Returns (all 0) | OS-11; `sales_revenue` OQ31-10 |
| `_pricing_snapshot_from_po_lines` | R1 | PS-01, PS-02, PS-05 |
| `_pricing_snapshot_from_po_lines` | R2 | PS-01, PS-03, PS-04 |
| `_pricing_snapshot_from_po_lines` | R3 | PS-01, PS-03, PS-04, PS-07, PS-08 |
| `_pricing_snapshot_from_po_lines` | R4 | PS-06 |
| `_pricing` | R1 | PRC-02, PRC-07, OQ32-09 |
| `_pricing` | R1a [BUG-2521] | PRC-08 |
| `_pricing` | R2 | PRC-01, PRC-02, PRC-03, PRC-04 |
| `_pricing` | R2a [BUG-2524] | PRC-05 (xfail), PRC-04 (pass part) |
| `_pricing` | R3 | PRC-03, PRC-06, PRC-07, GS-10 |
| `_pricing` | R4 | OQ32-01 … OQ32-09, OQ32-11, OQ32-16 |
| `_pricing` | R4b [BUG-2486] | OQ32-10, OQ32-12, OQ32-16, OQ32-17 (xfail); OQ32-08 (no workflow), OQ32-11 (earlier status), OQ32-13 (empty sequence), OQ32-14, OQ32-15 (other workspace's workflow) — pass. "No current status" gets no card: `current_status_id` is a required PO column (spec Notes) |
| `_pricing` | R4a [BUG-2521] | PRC-09 |
| `_supplier_stats` | R1 | SS-01, SS-02, SS-06 |
| `_supplier_stats` | R2 | SS-01, SS-03, SS-04, GS-10 |
| `_supplier_stats` | R2a [BUG-2521] | SS-09 |
| `_supplier_stats` | R3 [BUG-2520] | SS-07, SS-08 |
| `_supplier_stats` | R4 | SS-05 |
| `_supplier_stats` | R5 [BUG-2523] | SS-12; SS-10, SS-11 (non-strict) |
| `_supplier_period_snapshot` | R1 | SP-01, SP-02, SP-03 |
| `_supplier_period_snapshot` | R2 | SP-05 |
| `_supplier_period_snapshot` | R3 [BUG-2523] | SP-04; SP-07, SP-08, SS-12 |
| `_supplier_period_snapshot` | R4 | SP-06 |
| `_supplier_rows_from_po_lines` | R1 | SR-01, SR-02 |
| `_supplier_rows_from_po_lines` | R2 | SR-03, SR-04 |
| `_supplier_rows_from_po_lines` | R3 | SR-01, SR-05, SR-08, SR-19 |
| `_supplier_rows_from_po_lines` | R4 | SR-01, SR-05, SR-06, SR-07, SR-19 |
| `_supplier_rows_from_po_lines` | R4a [BUG-2524] | SR-09, SR-10 (xfail), SR-08 (pass part) |
| `_supplier_rows_from_po_lines` | R5 | SR-01, SR-11, SR-20 |
| `_supplier_rows_from_po_lines` | R5b | SR-19, SR-20 |
| `_supplier_rows_from_po_lines` | R5a [BUG-2524] | SR-13, SR-14 (xfail), SR-12 (pass part) |
| `_supplier_rows_from_po_lines` | R6 [BUG-2523] | SR-15, SR-17, SS-10, SS-11, SS-12; SR-18 (pass) |
| `_supplier_rows_from_po_lines` | R7 | SR-16 |
| `_pick_cheapest_supplier` | R1 | CH-01 … CH-06 |
| `_pick_cheapest_supplier` | Returns (the input row itself) | CH-01 |
| `_pick_cheapest_supplier` | R2 [BUG-2523] | CH-07 |
| `_pick_most_frequent_supplier` | R1 | MF-01 … MF-04, MF-07, MF-08 |
| `_pick_most_frequent_supplier` | Returns (the input row itself) | MF-02 |
| `_pick_most_frequent_supplier` | R2 [BUG-2523] | MF-05, MF-06 |
| `_usage` | R1 | US-01, US-02, US-03, US-18 |
| `_usage` | R2 [BUG-2525] | US-15, US-16, US-17 |
| `_usage` | R3 | US-02, US-03, US-04 |
| `_usage` | R4 [BUG-2522] | US-05 … US-09; US-10 … US-14 |
| `_usage` | R4a [BUG-2526] | US-19 … US-23 (xfail), US-18 (pass part) |
| `_usage` | R5 [BUG-2525] | US-15, US-16, US-17 |
| `_usage` | R6 [BUG-2520] | US-24 … US-29 |
| `_usage` | R7 | US-30 |
| `_resolve_order_link` | R1 | OL-01, OL-02, OL-03 |
| `_resolve_order_link` | R2 | OL-04, OL-05, OL-06, OL-07 |
| `_resolve_order_link` | R3 | OL-02, OL-03, OL-08 … OL-11 |
| `_resolve_order_link` | R4 | OL-12, OL-13, OL-14 |
| `_resolve_order_link` | R4a [BUG-2527] | OL-16 … OL-20 (xfail); OL-12 … OL-15 (stay unlinked, pass) |
| `_resolve_order_link` | R5 [BUG-2520] | OL-21 … OL-30, RA-19 |
| `_resolve_order_number` | R1 | ON-01, ON-02 |
| `_resolve_order_number` | R2 | ON-03 … ON-09 |
| `_resolve_order_number` | R3 [BUG-2520] | ON-10 … ON-14, RA-20 |
| `_activity_from_ledger` | R1 | AL-01, AL-02, RA-02 |
| `_activity_from_ledger` | R2 | AL-03 |
| `_activity_from_ledger` | R3 [BUG-2520 part] | AL-06, AL-07 (pass); AL-04, AL-05 (xfail, new `workspace_id`) |
| `_recent_activity` | R1 [BUG-640] | RA-09, RA-10, RA-11, RA-16; DP-10 |
| `_recent_activity` | R2 | RA-01 … RA-07 |
| `_recent_activity` | R3 [BUG-2529, BUG-1337] | RA-08, RA-09, RA-10, RA-12; RA-22, DP-11 |
| `_recent_activity` | R3a [BUG-2487] | RA-23, RA-24 |
| `_recent_activity` | R4 | RA-13, RA-14 |
| `_recent_activity` | R5 | RA-15 |
| `_recent_activity` | R6 [BUG-2520] | RA-17, RA-18 |
| `_recent_activity` | R7 [BUG-2528] | RA-21 |
