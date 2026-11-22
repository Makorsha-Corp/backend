# Test cases — `app/services/item_orders_service.py`

> **Spec:** `tests/unit/services/item_orders_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-10) — executor note (`item_orders_service.notes.md`): Expect lines name every bug a card needs: OQ33-01 BUG-2490 + BUG-2554, OQ33-02 BUG-2491 + BUG-2554, OQ33-09 BUG-2490 + BUG-2491. Parallel runs: `so` and `to` store their number with the per-process suffix **GN**, and **nums**, **numset**, **row(n)** read numbers through **base()** (Conventions), so no Then line changes. No card added or retired.
> **Revision:** 2 (2026-11-10) — spec round 2: owner answered OQ-33 (BUG-2490, BUG-2491) and gaps 1–4 were filled (`_purchase_rows` R12, `get_orders_for_item` R13, Facts "Date columns" and "Minimum rows"). Changed: section "Pending owner — OQ-33" becomes "Priced quantity and zero totals — BUG-2490, BUG-2491" (IDs kept): OQ33-01, OQ33-03 strict xfail BUG-2490; OQ33-02, OQ33-05 strict xfail BUG-2491; OQ33-04 stays pass (R7a). G-21, G-22 strict (tie key is in the Python sort, R13), 6 rows in G-21; no longer `Author: claude`. New: OQ33-06, OQ33-08 (the parts that hold today), OQ33-07 (half up on the priced quantity), OQ33-09 (priced quantity 0); G-35 (type rank beats id), G-36 (type, then id descending); P-21, T-08, W-11 (near-midnight `created_at` edges: the stored day); P-22, P-23, T-07, S-11, W-10 (row helpers called directly, `list[ItemOrderRowResponse]`). Builders checked against "Minimum rows" (no change needed). Gaps 1–4 closed. No card retired. Follow-up (same day): G-21, G-22, G-36 made non-strict (`Author: claude`; the database's tie order can match the expected one by chance); new strict G-37 feeds the Python sort a fixed tied input through a patched `_purchase_rows`; OQ33-07 Expect names BUG-2490 and BUG-2554.
> **Counts:** 128 cases · 92 expected-to-pass · 36 expected-to-fail (bugs; 3 non-strict) · 1 deferred

## Reviewer summary
- **Per callable:** `_dec` 4 · `_in_date_range` 2 · `_weighted_unit_price` 9 (3 bug) · `_build_po_destination_labels` 14 (4 bug) · `get_orders_for_item` 36 (6 bug) · `_purchase_rows` 23 (7 bug) · `_transfer_rows` 8 (1 bug) · `_sales_rows` 11 (3 bug) · `_work_rows` 11 (5 bug) · **priced quantity / zero totals (OQ-33 answered)** 9 (6 bug).
- **Depth:** full (money values, workspace isolation, voided / deleted rows, ordering and paging, date edges). Pure helpers get one card per rule and boundary.
- **OQ-33 (answered 2026-11-10):** partly priced, zero-priced and unpriced shapes stay in their own section (IDs `IOS-OQ33-nn`), now strict xfail on BUG-2490 (unit price = priced subtotal / priced quantity, half up) and BUG-2491 (a priced total of 0.00 shows 0.00). Parts that hold today and after (quantity, line total of a partly priced PO, empty line total of an unpriced PO, quantity 0) are pass cards there. Every other card still uses fully priced lines with a positive total.
- **Expected-to-fail (strict unless noted):** BUG-2550 6 (G-06, G-10, G-23, W-03, W-04, W-08), BUG-2551 4 (G-21, G-22, G-36 non-strict; G-37 strict), BUG-2552 1 (W-05), BUG-2553 1 (W-06), BUG-2554 5 (WP-07 … 09, P-19, S-09), BUG-2555 13 (DL-11 … 14, P-13 … 18, T-06, S-07, S-08), BUG-2490 4 (OQ33-01, 03, 07, 09), BUG-2491 2 (OQ33-02, 05). BUG-2556 is endpoint-only (deferred); at the service a lone bound stays ignored (G-13, G-14 pass).
- **Notable design choices:**
  - Per-type rules are mostly tested through `get_orders_for_item(order_type=…)`; each row helper also has a direct card for its return shape (spec R12).
  - Work orders: any live work order line in scope crashes today (BUG-2550). Pass cards keep the item off live work order lines, or filter by another type, or prove exclusion with an empty result (deleted line only, dates just outside, other workspaces). Voided / deleted work order cards are xfail for their own bug, failing today in the call.
  - BUG-2551: G-21, G-22 and G-36 build tied rows in the database and are non-strict (`Author: claude`): the database's tie order could match the expected one by chance. G-37 is the strict alarm: it patches `_purchase_rows` to return tied rows in ascending id order, which today's stable timestamp-only sort keeps, so it fails on every run until the fix.
  - G-35 gives the PO the smallest and the sales order the largest explicit id, so an id key ahead of the type rank fails; G-36 puts a transfer between two POs by id.
  - Dates from `created_at` use 12:00 on each edge day, and P-21, T-08, W-11 add 23:59:59.999999 / 00:00:00 on the edges: the stored day counts (spec Facts "Date columns").
  - Cards that need two fixes name both on the Expect line: OQ33-01, OQ33-07 (BUG-2490 + BUG-2554), OQ33-02 (BUG-2491 + BUG-2554), OQ33-09 (BUG-2490 + BUG-2491).
  - Every isolation card builds rows in W0 (lower ids) and W2 (higher ids); each HR-16 bug shape (account, status, storage, machine, component, foreign project) has its own card with a W0 and a W2 variant.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `IOS` = `app/services/item_orders_service.py`. `DC` _dec · `DR` _in_date_range · `WP` _weighted_unit_price · `DL` _build_po_destination_labels · `G` get_orders_for_item · `P` purchase rows · `T` transfer rows · `S` sales rows · `W` work rows · `OQ33` priced quantity and zero totals (OQ-33, answered: BUG-2490, BUG-2491).

**Imports.** `from app.services.item_orders_service import ItemOrdersService, item_orders_service, _dec, _in_date_range, _weighted_unit_price, _build_po_destination_labels`. `NotFoundError` (`app.core.exceptions`); `ItemOrderRowResponse` (`app.schemas.item_orders`). Models (`app.models.<module>`): `factory.Factory`, `machine.Machine`, `project.Project`, `project_component.ProjectComponent`, `account.Account`, `status.Status`, `item.Item`, `work_order_type.WorkOrderType`, `purchase_order.PurchaseOrder`, `purchase_order_item.PurchaseOrderItem`, `transfer_order.TransferOrder`, `transfer_order_item.TransferOrderItem`, `sales_order.SalesOrder`, `sales_order_item.SalesOrderItem`, `work_order.WorkOrder`, `work_order_item.WorkOrderItem`. `Decimal`, `InvalidOperation` (`decimal`); `date`, `datetime`, `timedelta`; `patch`; `event` (`sqlalchemy`); `os`.

**Fixed values.** `svc` = `item_orders_service`. PRE = `date(2026, 4, 30)`, START = `date(2026, 5, 1)`, MID = `date(2026, 5, 10)`, END = `date(2026, 5, 31)`, POST = `date(2026, 6, 1)`. CT = `datetime(2026, 5, 10, 9, 0, 0)`. **noon(d)** = `datetime(d.year, d.month, d.day, 12, 0, 0)`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. MISSING = `999999999`. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k` (an explicit row id passed as `id=`). `result` = what the When returns.

**Standing rows** (every test, no Given line; flushed in this order, so in each table W0 ids < W1 ids < W2 ids): W0, W1, W2 = `make_workspace(db)`; U1 = `make_profile(db)`. Then for each workspace X in (W0, W1, W2) with suffix x in (0, 1, 9):
- Fx = `Factory(workspace_id=X.id, name=…, abbreviation=…)`: F0 "Factory Zero"/"F0", F1 "Factory One"/"F1", F9 "Factory Nine"/"F9".
- Sx = `Status(workspace_id=X.id, name="Draft", comment="Stage")`. ACx = `Account(workspace_id=X.id, name=…)`: AC0 "Zero Co", AC1 "Acme", AC9 "Far Co". WTx = `WorkOrderType(workspace_id=X.id, name="Repair")`.
- Ix = `Item(workspace_id=X.id, name="Bolt", name_normalized="bolt", unit="pcs")`.
- Mx = `Machine(workspace_id=X.id, factory_id=Fx.id, name=…)`: M0 "Zero Press", M1 "Press 1", M9 "Far Press".
- PJx = `Project(workspace_id=X.id, factory_id=Fx.id, name=…, description="Main")`: PJ0 "Zero Build", PJ1 "Main Build", PJ9 "Far Build". Cx = `ProjectComponent(workspace_id=X.id, project_id=PJx.id, name=…)`: C0 "Base", C1 "Roof", C9 "Wing".
- W1 only, after the above: I2 = `Item(workspace_id=W1.id, name="Nut", name_normalized="nut", unit="pcs")`; S2 = `Status(workspace_id=W1.id, name="Closed", comment="Stage")`.

**Order builders** (Given rows built directly, flushed one at a time in the order written). The card names every value that differs after "but". "W0 x" / "W2 x" = builder x with every W1 standing row swapped for that workspace's (W1 → W0/W2, F1 → F0/F9, S1 → S0/S9, AC1 → AC0/AC9, WT1 → WT0/WT9).
- **po(n)** = `PurchaseOrder(workspace_id=W1.id, po_number=n, account_id=AC1.id, destination_type="storage", destination_id=F1.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=S1.id, created_by=U1.id, description="Steel order", order_date=MID, created_at=CT)`. **voided** po = `voided True`, `void_note "Void"`, `voided_at T0`, `voided_by U1.id`.
- **pl(P, I, q, sub)** = `PurchaseOrderItem(workspace_id=P.workspace_id, purchase_order_id=P.id, line_number=k, item_id=I.id, quantity_ordered=Decimal(q), line_subtotal=Decimal(sub))`, k = 1, 2, … per PO in the order written; `sub` `None` → `line_subtotal=None`.
- **to(n)** = `TransferOrder(workspace_id=W1.id, transfer_number=GN(n), source_location_type="storage", source_location_id=F1.id, destination_location_type="storage", destination_location_id=F1.id, current_status_id=S1.id, created_by=U1.id, created_at=CT)`.
- **tl(T, I, q)** = `TransferOrderItem(workspace_id=T.workspace_id, transfer_order_id=T.id, line_number=k, item_id=I.id, quantity=Decimal(q))`.
- **so(n)** = `SalesOrder(workspace_id=W1.id, sales_order_number=GN(n), account_id=AC1.id, factory_id=F1.id, order_date=MID, total_amount=Decimal("0.00"), current_status_id=S1.id, created_by=U1.id, description="Chairs", created_at=CT)`.
- **sl(S, I, q, t)** = `SalesOrderItem(workspace_id=S.workspace_id, sales_order_id=S.id, item_id=I.id, description="Line", quantity_ordered=Decimal(q), unit_price=Decimal("1.00"), line_total=Decimal(t))`; `I` `None` → `item_id=None` (a free-text line).
- **wo(n)** = `WorkOrder(workspace_id=W1.id, work_order_number=n, title="Fix press", factory_id=F1.id, work_order_type_id=WT1.id, created_by=U1.id, status="DRAFT", created_at=CT)`. **deleted** wo = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **wl(W, I, q)** = `WorkOrderItem(workspace_id=W.workspace_id, work_order_id=W.id, item_id=I.id, quantity=Decimal(q))`; a **deleted** line = `is_deleted True`.

**Priced lines.** Outside the section "Priced quantity and zero totals" every PO and sales line of the item is priced with a positive subtotal; partly priced, zero-priced and unpriced POs (and zero-priced sales orders) appear only there.

**Direct row-helper calls.** `svc._purchase_rows(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)` (likewise `_transfer_rows`, `_sales_rows`, `_work_rows`, without `exclude_purchase_order_id`); `result` is a plain list.

**Builders** carry every NOT NULL column without a default that the spec's "Minimum rows" lists.

**Named checks.**
- **base(x)** = `x.removesuffix(f"-{os.getpid()}")` (drops the GN suffix; other numbers unchanged). **nums** = `[base(r.order_number) for r in result.items]` (list order). **numset** = `{base(r.order_number) for r in result.items}`. **row(n)** = the one item of `result.items` with `base(order_number) == n`. A direct helper card that reads `result[k].order_number` of a sales or transfer row compares `base(result[k].order_number)`.
- **recorder** = a Given step: `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `statement`; removed with `event.remove` right after the When. `statement:` lines check `stmts`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **commit point** = `db.commit()` after the Given lines above it; lines marked "(after the commit point)" run after it and are not flushed.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call. `session:` lines check `db` directly.

**Calls.** Every list call passes `limit=1000` unless the card names `limit`. All arguments after `db` by keyword.

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`; non-strict cards use `strict=False`. Write the call and checks as shown.

**Parallel runs.** `transfer_number` and `sales_order_number` are unique across all workspaces today (BUG-726 and siblings). **GN(n)** = `f"{n}-{os.getpid()}"`: the `to` and `so` builders store `GN(n)` for the card's number n, so two processes never insert the same number. PO and work order numbers are unique per workspace and are stored as written.

**Race simulations.** None.

**Fixed-input patch (BUG-2551 only).** IOS-G-37 replaces `_purchase_rows` with a fixed list of tied rows so the Python sort (spec R13) sees a known input order; Python's sort with `reverse=True` keeps tied rows in input order, so ascending ids fail today on every run. Used nowhere else. G-21, G-22 and G-36 rely on the database's row order for ties and are non-strict for that reason.

## `_dec`

### IOS-DC-01 — None becomes zero
- **Rules:** `_dec` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(None)`.

**Then**
1. returns: `result == Decimal(0)`, `isinstance(result, Decimal)`.

### IOS-DC-02 — a Decimal keeps its scale
- **Rules:** `_dec` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _dec(Decimal("10.00"))`.

**Then**
1. returns: `str(result) == "10.00"`.

### IOS-DC-03 — a float goes through its text, not its binary value
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

### IOS-DC-04 — non-numeric text raises InvalidOperation
- **Rules:** `_dec` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `_dec("abc")`.

**Then**
1. raises: `InvalidOperation`.

## `_in_date_range`

### IOS-DR-01 — both ends are included, the days outside are not
- **Rules:** `_in_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date PRE`.
2. PB = po("PO-B") but `order_date START`.
3. PC = po("PO-C") but `order_date END`.
4. PD = po("PO-D") but `order_date POST`.

**When**
- `result = db.query(PurchaseOrder).filter(PurchaseOrder.workspace_id == W1.id, _in_date_range(PurchaseOrder.order_date, START, END)).all()`.

**Then**
1. returns: `{p.po_number for p in result} == {"PO-B", "PO-C"}`.

### IOS-DR-02 — a reversed range matches nothing
- **Rules:** `_in_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date START`.
2. PB = po("PO-B") but `order_date END`.

**When**
- `result = db.query(PurchaseOrder).filter(PurchaseOrder.workspace_id == W1.id, _in_date_range(PurchaseOrder.order_date, END, START)).all()`.

**Then**
1. returns: `result == []`.

## `_weighted_unit_price`

### IOS-WP-01 — quantity 0 gives None
- **Rules:** `_weighted_unit_price` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("50.00"), Decimal("0"))`.

**Then**
1. returns: `result is None`.

### IOS-WP-02 — a negative quantity gives None
- **Rules:** `_weighted_unit_price` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("50.00"), Decimal("-1"))`.

**Then**
1. returns: `result is None`.

### IOS-WP-03 — the smallest positive quantity divides
- **Rules:** `_weighted_unit_price` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("1.00"), Decimal("0.01"))`.

**Then**
1. returns: `result == Decimal("100")`.

### IOS-WP-04 — a zero total gives zero, not None
- **Rules:** `_weighted_unit_price` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("0"), Decimal("4"))`.

**Then**
1. returns: `result is not None`.
2. returns: `result == Decimal("0")`.

### IOS-WP-05 — total divided by quantity
- **Rules:** `_weighted_unit_price` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("50.00"), Decimal("10.00"))`.

**Then**
1. returns: `result == Decimal("5.00")`, `isinstance(result, Decimal)`.

### IOS-WP-06 — a repeating quotient is within a cent of the rounded value
- **Rules:** `_weighted_unit_price` R2, R3 (regression part of BUG-2554)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("100.00"), Decimal("3"))`.

**Then**
1. returns: `Decimal("33.33") <= result < Decimal("33.34")`.

### IOS-WP-07 — the price is rounded to two places
- **Rules:** `_weighted_unit_price` R3 [BUG-2554]
- **Kind:** bug
- **Expect:** xfail BUG-2554
- **Fails today on:** Then 1 (today `33.33333333333333333333333333`)

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("100.00"), Decimal("3"))`.

**Then**
1. returns: `str(result) == "33.33"`.

### IOS-WP-08 — a half cent rounds up, not to even
- **Rules:** `_weighted_unit_price` R3 [BUG-2554]
- **Kind:** bug
- **Expect:** xfail BUG-2554
- **Fails today on:** Then 1 (today `0.125`)

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("0.25"), Decimal("2"))`.

**Then**
1. returns: `str(result) == "0.13"`.

### IOS-WP-09 — a negative half cent rounds away from zero
- **Rules:** `_weighted_unit_price` R3 [BUG-2554]
- **Kind:** bug
- **Expect:** xfail BUG-2554
- **Fails today on:** Then 1 (today `-0.125`)

**Given**
1. Standing rows only.

**When**
- `result = _weighted_unit_price(Decimal("-0.25"), Decimal("2"))`.

**Then**
1. returns: `str(result) == "-0.13"`.

## `_build_po_destination_labels`

### IOS-DL-01 — only falsy ids: empty dict, nothing read
- **Rules:** `_build_po_destination_labels` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. recorder.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("storage", 0), ("machine", None), ("project", 0)])`.

**Then**
1. returns: `result == {}`.
2. statement: `stmts == []`.

### IOS-DL-02 — falsy ids are dropped, real ones kept
- **Rules:** `_build_po_destination_labels` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("storage", 0), ("storage", F1.id)])`.

**Then**
1. returns: `result == {("storage", F1.id): "Storage (Factory One)"}`.

### IOS-DL-03 — storage is labelled with the factory name
- **Rules:** `_build_po_destination_labels` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("storage", F1.id)])`.

**Then**
1. returns: `result[("storage", F1.id)] == "Storage (Factory One)"`.

### IOS-DL-04 — machine is labelled with the machine name
- **Rules:** `_build_po_destination_labels` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("machine", M1.id)])`.

**Then**
1. returns: `result == {("machine", M1.id): "Machine (Press 1)"}`.

### IOS-DL-05 — project is labelled with project and component names
- **Rules:** `_build_po_destination_labels` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("project", C1.id)])`.

**Then**
1. returns: `result == {("project", C1.id): "Project · Main Build / Roof"}`.

### IOS-DL-06 — a deleted factory and a deleted machine are still named
- **Rules:** `_build_po_destination_labels` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Old Plant", abbreviation="OP", is_deleted=True)`.
2. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 4", is_active=False, is_deleted=True)`.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("storage", FD.id), ("machine", MD.id)])`.

**Then**
1. returns: `result[("storage", FD.id)] == "Storage (Old Plant)"`.
2. returns: `result[("machine", MD.id)] == "Machine (Press 4)"`.

### IOS-DL-07 — ids found nowhere get the fallback labels
- **Rules:** `_build_po_destination_labels` R6, R7 (missing id keeps R6)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only (no row has id MISSING).

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("storage", MISSING), ("machine", MISSING), ("project", MISSING)])`.

**Then**
1. returns: `result[("storage", MISSING)] == "Storage"`.
2. returns: `result[("machine", MISSING)] == "Machine #999999999"`.
3. returns: `result[("project", MISSING)] == "Component #999999999"`.
4. returns: `len(result) == 3`.

### IOS-DL-08 — an unknown type is labelled type and id
- **Rules:** `_build_po_destination_labels` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("weird", 7)])`.

**Then**
1. returns: `result == {("weird", 7): "weird #7"}`.

### IOS-DL-09 — a pair given twice appears once
- **Rules:** `_build_po_destination_labels` R6 (duplicates)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("machine", M1.id), ("storage", F1.id), ("machine", M1.id)])`.

**Then**
1. returns: `result == {("machine", M1.id): "Machine (Press 1)", ("storage", F1.id): "Storage (Factory One)"}`.

### IOS-DL-10 — another workspace's names never appear in a label
- **Rules:** `_build_po_destination_labels` R7 (regression part of BUG-2555)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("storage", F0.id), ("storage", F9.id), ("machine", M0.id), ("machine", M9.id), ("project", C0.id), ("project", C9.id)])`.

**Then**
1. returns: `not any("Factory Zero" in v or "Factory Nine" in v for v in result.values())`.
2. returns: `not any("Zero Press" in v or "Far Press" in v for v in result.values())`.
3. returns: `not any(s in v for v in result.values() for s in ("Zero Build", "Far Build", "Base", "Wing"))`.

### IOS-DL-11 — another workspace's factory gets no label
- **Rules:** `_build_po_destination_labels` R7 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today both keys map to "Storage")

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("storage", F0.id), ("storage", F9.id), ("storage", F1.id)])`.

**Then**
1. returns: `("storage", F0.id) not in result`.
2. returns: `("storage", F9.id) not in result`.
3. returns: `result[("storage", F1.id)] == "Storage (Factory One)"`.

### IOS-DL-12 — another workspace's machine gets no label
- **Rules:** `_build_po_destination_labels` R7 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today "Machine #<id>")

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("machine", M0.id), ("machine", M9.id)])`.

**Then**
1. returns: `("machine", M0.id) not in result`.
2. returns: `("machine", M9.id) not in result`.

### IOS-DL-13 — another workspace's component gets no label
- **Rules:** `_build_po_destination_labels` R7 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today "Component #<id>")

**Given**
1. Standing rows only.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("project", C0.id), ("project", C9.id)])`.

**Then**
1. returns: `("project", C0.id) not in result`.
2. returns: `("project", C9.id) not in result`.

### IOS-DL-14 — this workspace's component under another workspace's project gets no label
- **Rules:** `_build_po_destination_labels` R7 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today "Project · Far Build / Stray" etc.)

**Given**
1. CX0 = `ProjectComponent(workspace_id=W1.id, project_id=PJ0.id, name="Annex")`.
2. CX9 = `ProjectComponent(workspace_id=W1.id, project_id=PJ9.id, name="Stray")`.

**When**
- `result = _build_po_destination_labels(db, workspace_id=W1.id, destinations=[("project", CX0.id), ("project", CX9.id)])`.

**Then**
1. returns: `("project", CX0.id) not in result`.
2. returns: `("project", CX9.id) not in result`.

## `ItemOrdersService.get_orders_for_item`

### IOS-G-01 — an unknown item is 404
- **Rules:** `get_orders_for_item` R1; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `svc.get_orders_for_item(db, workspace_id=W1.id, item_id=MISSING, limit=1000)`.

**Then**
1. raises: `NotFoundError`, `exc.value.status_code == 404`, `exc.value.detail == "Item with ID 999999999 not found"`.
2. session: `not db.new and not db.dirty and not db.deleted`.

### IOS-G-02 — an item of the lower workspace is 404 and nothing else is read
- **Rules:** `get_orders_for_item` R1; Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po("PO-Z").
2. pl(P0, I0, "1.00", "5.00").
3. recorder.

**When**
- `svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I0.id, limit=1000)`.

**Then**
1. raises: `NotFoundError`, `exc.value.status_code == 404`, `exc.value.detail == f"Item with ID {I0.id} not found"`.
2. statement: `not any("purchase_orders" in s for s in stmts)`.
3. statement: `not any("sales_orders" in s or "transfer_orders" in s or "work_orders" in s for s in stmts)`.

### IOS-G-03 — an item of the higher workspace is 404
- **Rules:** `get_orders_for_item` R1; Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 po("PO-N").
2. pl(P9, I9, "1.00", "5.00").

**When**
- `svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I9.id, limit=1000)`.

**Then**
1. raises: `NotFoundError`, `exc.value.status_code == 404`, `exc.value.detail == f"Item with ID {I9.id} not found"`.

### IOS-G-04 — a deleted item still answers with its orders
- **Rules:** `get_orders_for_item` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. ID = `Item(workspace_id=W1.id, name="Old bolt", name_normalized="old bolt", unit="pcs", is_active=False)`.
2. P1 = po("PO-1").
3. pl(P1, ID, "2.00", "10.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=ID.id, limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-G-05 — no type: purchase, transfer and sales rows together
- **Rules:** `get_orders_for_item` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1") but `order_date date(2026, 5, 12)`.
2. pl(P1, I1, "1.00", "5.00").
3. T1 = to("TO-1") but `created_at noon(date(2026, 5, 11))`.
4. tl(T1, I1, "2.00").
5. S1 = so("SO-1") but `order_date MID`.
6. sl(S1, I1, "3.00", "30.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `[(r.order_type, base(r.order_number)) for r in result.items] == [("purchase_order", "PO-1"), ("transfer_order", "TO-1"), ("sales_order", "SO-1")]`.

### IOS-G-06 — no type: a work order row comes with the others
- **Rules:** `get_orders_for_item` R3; `_work_rows` R5 [BUG-2550]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2550
- **Fails today on:** Then 1 (the call raises AttributeError: status read as an enum)

**Given**
1. P1 = po("PO-1") but `order_date date(2026, 5, 13)`.
2. pl(P1, I1, "1.00", "5.00").
3. T1 = to("TO-1") but `created_at noon(date(2026, 5, 12))`.
4. tl(T1, I1, "2.00").
5. S1 = so("SO-1") but `order_date date(2026, 5, 11)`.
6. sl(S1, I1, "3.00", "30.00").
7. WO1 = wo("WO-1") but `created_at noon(MID)`.
8. wl(WO1, I1, "4.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 4`.
2. returns: `nums == ["PO-1", "TO-1", "SO-1", "WO-1"]`.

### IOS-G-07 — type purchase: only purchase rows, other types not read
- **Rules:** `get_orders_for_item` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "1.00", "5.00").
3. T1 = to("TO-1").
4. tl(T1, I1, "2.00").
5. S1 = so("SO-1").
6. sl(S1, I1, "3.00", "30.00").
7. WO1 = wo("WO-1").
8. wl(WO1, I1, "4.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-G-08 — type transfer: only transfer rows
- **Rules:** `get_orders_for_item` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "1.00", "5.00").
3. T1 = to("TO-1").
4. tl(T1, I1, "2.00").
5. S1 = so("SO-1").
6. sl(S1, I1, "3.00", "30.00").
7. WO1 = wo("WO-1").
8. wl(WO1, I1, "4.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["TO-1"]`.

### IOS-G-09 — type sales: only sales rows
- **Rules:** `get_orders_for_item` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "1.00", "5.00").
3. T1 = to("TO-1").
4. tl(T1, I1, "2.00").
5. S1 = so("SO-1").
6. sl(S1, I1, "3.00", "30.00").
7. WO1 = wo("WO-1").
8. wl(WO1, I1, "4.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["SO-1"]`.

### IOS-G-10 — type work: only work rows
- **Rules:** `get_orders_for_item` R3; `_work_rows` R5 [BUG-2550]
- **Kind:** bug
- **Expect:** xfail BUG-2550
- **Fails today on:** Then 1 (the call raises AttributeError: status read as an enum)

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "1.00", "5.00").
3. T1 = to("TO-1").
4. tl(T1, I1, "2.00").
5. S1 = so("SO-1").
6. sl(S1, I1, "3.00", "30.00").
7. WO1 = wo("WO-1").
8. wl(WO1, I1, "4.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["WO-1"]`.

### IOS-G-11 — a reversed range gives no rows
- **Rules:** `get_orders_for_item` R4, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1") but `order_date MID`.
2. pl(P1, I1, "1.00", "5.00").
3. T1 = to("TO-1") but `created_at noon(MID)`.
4. tl(T1, I1, "2.00").
5. S1 = so("SO-1") but `order_date MID`.
6. sl(S1, I1, "3.00", "30.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=END, to_date=START, limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-G-12 — a one-day range keeps that day only
- **Rules:** `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date date(2026, 5, 9)`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `order_date MID`.
4. pl(PB, I1, "1.00", "5.00").
5. PC = po("PO-C") but `order_date date(2026, 5, 11)`.
6. pl(PC, I1, "1.00", "5.00").
7. S1 = so("SO-1") but `order_date MID`.
8. sl(S1, I1, "3.00", "30.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=MID, to_date=MID, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"PO-B", "SO-1"}`.

### IOS-G-13 — from_date alone is ignored at the service
- **Rules:** `get_orders_for_item` R4a (service part)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date PRE`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `order_date POST`.
4. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, from_date=POST, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"PO-A", "PO-B"}`.

### IOS-G-14 — to_date alone is ignored at the service
- **Rules:** `get_orders_for_item` R4a (service part)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date PRE`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `order_date POST`.
4. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, to_date=PRE, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"PO-A", "PO-B"}`.

### IOS-G-15 — the excluded PO is left out, POs on both sides of its id stay
- **Rules:** `get_orders_for_item` R5; `_purchase_rows` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = po("PO-A").
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B").
4. pl(PB, I1, "1.00", "5.00").
5. PC = po("PO-C").
6. pl(PC, I1, "1.00", "5.00").
7. S1 = so("SO-1").
8. sl(S1, I1, "3.00", "30.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, exclude_purchase_order_id=PB.id, limit=1000)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `numset == {"PO-A", "PO-C", "SO-1"}`.

### IOS-G-16 — exclude 0 leaves everything in
- **Rules:** `get_orders_for_item` R5; `_purchase_rows` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A").
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B").
4. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, exclude_purchase_order_id=0, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"PO-A", "PO-B"}`.

### IOS-G-17 — an unknown exclude id leaves everything in
- **Rules:** `get_orders_for_item` R5; `_purchase_rows` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A").
2. pl(PA, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, exclude_purchase_order_id=MISSING, limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-A"]`.

### IOS-G-18 — exclude touches POs only: a transfer with the same id stays
- **Rules:** `get_orders_for_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PX = po("PO-X") but `id XID(1)`.
2. pl(PX, I1, "1.00", "5.00").
3. TX = to("TO-X") but `id XID(1)`.
4. tl(TX, I1, "2.00").
5. SX = so("SO-X") but `id XID(1)`.
6. sl(SX, I1, "3.00", "30.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, exclude_purchase_order_id=XID(1), limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"TO-X", "SO-X"}`.

### IOS-G-19 — date newest first, then created_at newest first
- **Rules:** `get_orders_for_item` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. P2 = po("PO-2") but `order_date date(2026, 5, 11)`, `created_at datetime(2026, 5, 11, 8, 0, 0)`.
2. pl(P2, I1, "1.00", "5.00").
3. S1 = so("SO-1") but `order_date date(2026, 5, 11)`, `created_at datetime(2026, 5, 20, 9, 0, 0)`.
4. sl(S1, I1, "1.00", "5.00").
5. T1 = to("TO-1") but `created_at datetime(2026, 5, 11, 10, 0, 0)`.
6. tl(T1, I1, "1.00").
7. P1 = po("PO-1") but `order_date date(2026, 5, 12)`, `created_at datetime(2026, 5, 1, 8, 0, 0)`.
8. pl(P1, I1, "1.00", "5.00").
9. P3 = po("PO-3") but `order_date date(2026, 5, 9)`, `created_at datetime(2026, 5, 30, 8, 0, 0)`.
10. pl(P3, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 5`.
2. returns: `nums == ["PO-1", "SO-1", "TO-1", "PO-2", "PO-3"]`.

### IOS-G-20 — a full tie across types keeps purchase, transfer, sales
- **Rules:** `get_orders_for_item` R6 [BUG-2551] (type key, holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = so("SO-1") but `order_date MID`, `created_at CT`.
2. sl(S1, I1, "1.00", "5.00").
3. T1 = to("TO-1") but `created_at CT`.
4. tl(T1, I1, "1.00").
5. P1 = po("PO-1") but `order_date MID`, `created_at CT`.
6. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `nums == ["PO-1", "TO-1", "SO-1"]`.

### IOS-G-21 — a full tie inside one type is broken by order id descending
- **Rules:** `get_orders_for_item` R6 [BUG-2551]
- **Kind:** bug
- **Expect:** xfail BUG-2551 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (tied POs come in the database's row order, not by id descending)

**Given**
1. PB = po("PO-B") but `id XID(2)`, `order_date MID`, `created_at CT`.
2. pl(PB, I1, "1.00", "5.00").
3. PA = po("PO-A") but `id XID(1)`, `order_date MID`, `created_at CT`.
4. pl(PA, I1, "1.00", "5.00").
5. PD = po("PO-D") but `id XID(4)`, `order_date MID`, `created_at CT`.
6. pl(PD, I1, "1.00", "5.00").
7. PC = po("PO-C") but `id XID(3)`, `order_date MID`, `created_at CT`.
8. pl(PC, I1, "1.00", "5.00").
9. PF = po("PO-F") but `id XID(6)`, `order_date MID`, `created_at CT`.
10. pl(PF, I1, "1.00", "5.00").
11. PE = po("PO-E") but `id XID(5)`, `order_date MID`, `created_at CT`.
12. pl(PE, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 6`.
2. returns: `nums == ["PO-F", "PO-E", "PO-D", "PO-C", "PO-B", "PO-A"]`.

### IOS-G-22 — a page across a tie takes the rows by order id descending
- **Rules:** `get_orders_for_item` R6 [BUG-2551], R8
- **Kind:** bug
- **Expect:** xfail BUG-2551 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (tied rows in the database's row order, not by id descending)

**Given**
1. PC = po("PO-C") but `id XID(3)`, `order_date MID`, `created_at CT`.
2. pl(PC, I1, "1.00", "5.00").
3. PA = po("PO-A") but `id XID(1)`, `order_date MID`, `created_at CT`.
4. pl(PA, I1, "1.00", "5.00").
5. PE = po("PO-E") but `id XID(5)`, `order_date MID`, `created_at CT`.
6. pl(PE, I1, "1.00", "5.00").
7. PB = po("PO-B") but `id XID(2)`, `order_date MID`, `created_at CT`.
8. pl(PB, I1, "1.00", "5.00").
9. PD = po("PO-D") but `id XID(4)`, `order_date MID`, `created_at CT`.
10. pl(PD, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, skip=1, limit=2)`.

**Then**
1. returns: `result.total == 5`.
2. returns: `nums == ["PO-D", "PO-C"]`.

### IOS-G-23 — in a full tie the work order comes last
- **Rules:** `get_orders_for_item` R6 [BUG-2551]; `_work_rows` R5 [BUG-2550]
- **Kind:** bug
- **Expect:** xfail BUG-2550
- **Fails today on:** Then 1 (the call raises AttributeError: status read as an enum)

**Given**
1. WO1 = wo("WO-1") but `created_at CT`.
2. wl(WO1, I1, "1.00").
3. S1 = so("SO-1") but `order_date MID`, `created_at CT`.
4. sl(S1, I1, "1.00", "5.00").
5. P1 = po("PO-1") but `order_date MID`, `created_at CT`.
6. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `nums == ["PO-1", "SO-1", "WO-1"]`.

### IOS-G-24 — skip 2, limit 3 of 7
- **Rules:** `get_orders_for_item` R7, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Seven POs PO-1 … PO-7 = po("PO-k") but `order_date date(2026, 5, 10 + k)` for k = 1 … 7, each with pl(POk, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, skip=2, limit=3)`.

**Then**
1. returns: `result.total == 7`.
2. returns: `nums == ["PO-5", "PO-4", "PO-3"]`.

### IOS-G-25 — skip one before the end gives the last row
- **Rules:** `get_orders_for_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Seven POs PO-1 … PO-7 = po("PO-k") but `order_date date(2026, 5, 10 + k)` for k = 1 … 7, each with pl(POk, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, skip=6, limit=1000)`.

**Then**
1. returns: `result.total == 7`.
2. returns: `nums == ["PO-1"]`.

### IOS-G-26 — skip at the end gives an empty page
- **Rules:** `get_orders_for_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Seven POs PO-1 … PO-7 = po("PO-k") but `order_date date(2026, 5, 10 + k)` for k = 1 … 7, each with pl(POk, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, skip=7, limit=1000)`.

**Then**
1. returns: `result.total == 7`.
2. returns: `result.items == []`.

### IOS-G-27 — limit 0 gives an empty page, total unchanged
- **Rules:** `get_orders_for_item` R7, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Seven POs PO-1 … PO-7 = po("PO-k") but `order_date date(2026, 5, 10 + k)` for k = 1 … 7, each with pl(POk, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=0)`.

**Then**
1. returns: `result.total == 7`.
2. returns: `result.items == []`.

### IOS-G-28 — limit 1 gives the newest row
- **Rules:** `get_orders_for_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Seven POs PO-1 … PO-7 = po("PO-k") but `order_date date(2026, 5, 10 + k)` for k = 1 … 7, each with pl(POk, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1)`.

**Then**
1. returns: `result.total == 7`.
2. returns: `nums == ["PO-7"]`.

### IOS-G-29 — the default limit is 50
- **Rules:** `get_orders_for_item` R8 (default `limit=50`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 POs PO-1 … PO-51 = po("PO-k") but `order_date date(2026, 1, 1) + timedelta(days=k)` for k = 1 … 51, each with pl(POk, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id)` (no `skip`, no `limit`).

**Then**
1. returns: `result.total == 51`.
2. returns: `len(result.items) == 50`.
3. returns: `"PO-1" not in nums`.
4. returns: `nums[0] == "PO-51"`.

### IOS-G-30 — a voided PO is filtered before paging
- **Rules:** `get_orders_for_item` R7, R8; `_purchase_rows` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PV = voided po("PO-V") but `order_date date(2026, 5, 20)`.
2. pl(PV, I1, "1.00", "5.00").
3. PA = po("PO-A") but `order_date date(2026, 5, 15)`.
4. pl(PA, I1, "1.00", "5.00").
5. PB = po("PO-B") but `order_date date(2026, 5, 14)`.
6. pl(PB, I1, "1.00", "5.00").
7. PC = po("PO-C") but `order_date date(2026, 5, 13)`.
8. pl(PC, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, skip=1, limit=1)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `nums == ["PO-B"]`.

### IOS-G-31 — another workspace's order is filtered before paging
- **Rules:** `get_orders_for_item` R7, R8, R10
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po("PO-Z") but `order_date date(2026, 5, 21)`.
2. pl(P0, I1, "1.00", "5.00").
3. PA = po("PO-A") but `order_date date(2026, 5, 15)`.
4. pl(PA, I1, "1.00", "5.00").
5. PB = po("PO-B") but `order_date date(2026, 5, 14)`.
6. pl(PB, I1, "1.00", "5.00").
7. PC = po("PO-C") but `order_date date(2026, 5, 13)`.
8. pl(PC, I1, "1.00", "5.00").
9. P9 = W2 po("PO-N") but `order_date date(2026, 5, 20)`.
10. pl(P9, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, skip=1, limit=1)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `nums == ["PO-B"]`.

### IOS-G-32 — an item with no orders gives an empty list
- **Rules:** `get_orders_for_item` R9; `_purchase_rows` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I2, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-G-33 — a PO with two lines of the item is one row
- **Rules:** `get_orders_for_item` R11; `_purchase_rows` R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "4.00", "20.00").
3. pl(P1, I1, "6.00", "30.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `row("PO-1").quantity == Decimal("10.00")`.
3. returns: `row("PO-1").line_total == Decimal("50.00")`.
4. returns: `row("PO-1").unit_price == Decimal("5.00")`.

### IOS-G-34 — nothing is written, committed or rolled back; pending changes stay
- **Rules:** `get_orders_for_item` R12
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "1.00", "5.00").
3. commit point.
4. (after the commit point) `db.add(Item(workspace_id=W1.id, name="Spare", name_normalized="spare", unit="pcs"))`.
5. (after the commit point) `AC1.name = "Changed"`.

**When**
- spies; `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. session: `len(db.new) == 1`.
3. session: `AC1 in db.dirty`, `len(db.dirty) == 1`.
4. session: `not db.deleted`.
5. session: `AC1.name == "Changed"`.
6. mock called: `cm.call_count == 0`, `rb.call_count == 0`.

### IOS-G-35 — in a full tie the type rank comes before the order id
- **Rules:** `get_orders_for_item` R6 [BUG-2551] (type key, holds today), R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = so("SO-1") but `id XID(5)`, `order_date MID`, `created_at CT`.
2. sl(S1, I1, "1.00", "5.00").
3. T1 = to("TO-1") but `id XID(3)`, `created_at CT`.
4. tl(T1, I1, "1.00").
5. P1 = po("PO-1") but `id XID(1)`, `order_date MID`, `created_at CT`.
6. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `nums == ["PO-1", "TO-1", "SO-1"]`.

### IOS-G-36 — in a full tie: type rank first, then order id descending inside the type
- **Rules:** `get_orders_for_item` R6 [BUG-2551], R13
- **Kind:** bug
- **Expect:** xfail BUG-2551 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (the two tied POs come in the database's row order, PO-1 first)

**Given**
1. P1 = po("PO-1") but `id XID(1)`, `order_date MID`, `created_at CT`.
2. pl(P1, I1, "1.00", "5.00").
3. T4 = to("TO-4") but `id XID(4)`, `created_at CT`.
4. tl(T4, I1, "1.00").
5. P7 = po("PO-7") but `id XID(7)`, `order_date MID`, `created_at CT`.
6. pl(P7, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `nums == ["PO-7", "PO-1", "TO-4"]`.

### IOS-G-37 — a fixed tied input in ascending id order comes out by order id descending
- **Rules:** `get_orders_for_item` R6 [BUG-2551], R13
- **Kind:** bug
- **Expect:** xfail BUG-2551
- **Author:** claude
- **Fails today on:** Then 2 (the stable timestamp-only sort keeps the input order PO-1, PO-2, PO-3)

**Given**
1. No order rows exist in W1 (the transfer, sales and work helpers find nothing).
2. RK(k) = `ItemOrderRowResponse(order_type="purchase_order", order_id=k, order_number=f"PO-{k}", order_date=MID, quantity=Decimal("1.00"), unit_price=Decimal("5.00"), line_total=Decimal("5.00"), status_name="Draft", account_name=None, destination_label=None, created_at=CT)`.
3. **fixed input**: `patch.object(ItemOrdersService, "_purchase_rows", return_value=[RK(1), RK(2), RK(3)])` around the When.

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `nums == ["PO-3", "PO-2", "PO-1"]`.

## `ItemOrdersService._purchase_rows` (through `get_orders_for_item`)

### IOS-P-01 — every field of a purchase row
- **Rules:** `_purchase_rows` R1, R5, R6, R9; `get_orders_for_item` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1") but `order_date MID`.
2. pl(P1, I1, "10.00", "50.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `len(result.items) == 1`, `result.total == 1`.
2. returns: `row("PO-1").order_type == "purchase_order"`, `row("PO-1").order_id == P1.id`.
3. returns: `row("PO-1").order_date == MID`.
4. returns: `row("PO-1").quantity == Decimal("10.00")`.
5. returns: `row("PO-1").unit_price == Decimal("5.00")`.
6. returns: `row("PO-1").line_total == Decimal("50.00")`.
7. returns: `row("PO-1").status_name == "Draft"`, `row("PO-1").account_name == "Acme"`.
8. returns: `row("PO-1").destination_label == "Storage (Factory One)"`.
9. re-read P1: `row("PO-1").created_at == P1.created_at` (after `db.refresh(P1)`).

### IOS-P-02 — lines of other items are ignored
- **Rules:** `_purchase_rows` R1, R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "2.00", "10.00").
3. pl(P1, I2, "5.00", "99.00").
4. P2 = po("PO-2").
5. pl(P2, I2, "1.00", "7.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`, `nums == ["PO-1"]`.
2. returns: `row("PO-1").quantity == Decimal("2.00")`.
3. returns: `row("PO-1").line_total == Decimal("10.00")`.

### IOS-P-03 — a voided PO is left out
- **Rules:** `_purchase_rows` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. PV = voided po("PO-V").
2. pl(PV, I1, "1.00", "5.00").
3. P1 = po("PO-1").
4. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-P-04 — no order_date: the date of created_at is used
- **Rules:** `_purchase_rows` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1") but `order_date None`, `created_at noon(date(2026, 5, 11))`.
2. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").order_date == date(2026, 5, 11)`.

### IOS-P-05 — no order_date: the range filters on the created_at day, both edges
- **Rules:** `_purchase_rows` R3; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date None`, `created_at noon(PRE)`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `order_date None`, `created_at noon(START)`.
4. pl(PB, I1, "1.00", "5.00").
5. PC = po("PO-C") but `order_date None`, `created_at noon(END)`.
6. pl(PC, I1, "1.00", "5.00").
7. PD = po("PO-D") but `order_date None`, `created_at noon(POST)`.
8. pl(PD, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"PO-B", "PO-C"}`.

### IOS-P-06 — order_date range, both edges
- **Rules:** `_purchase_rows` R3; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date PRE`, `created_at noon(START)`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `order_date START`, `created_at noon(PRE)`.
4. pl(PB, I1, "1.00", "5.00").
5. PC = po("PO-C") but `order_date END`, `created_at noon(POST)`.
6. pl(PC, I1, "1.00", "5.00").
7. PD = po("PO-D") but `order_date POST`, `created_at noon(END)`.
8. pl(PD, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"PO-B", "PO-C"}`.

### IOS-P-07 — quantity is ordered, not received
- **Rules:** `_purchase_rows` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. PL = pl(P1, I1, "10.00", "50.00") but `quantity_received Decimal("4.00")`.

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").quantity == Decimal("10.00")`.

### IOS-P-08 — no account: account_name None
- **Rules:** `_purchase_rows` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1") but `account_id None`.
2. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `row("PO-1").account_name is None`.

### IOS-P-09 — destination id 0: destination_label None
- **Rules:** `_purchase_rows` R9; `_build_po_destination_labels` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1") but `destination_id 0`.
2. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `row("PO-1").destination_label is None`.

### IOS-P-10 — machine and project destinations reach the row
- **Rules:** `_purchase_rows` R9; `_build_po_destination_labels` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. PM = po("PO-M") but `destination_type "machine"`, `destination_id M1.id`.
2. pl(PM, I1, "1.00", "5.00").
3. PJ = po("PO-J") but `destination_type "project"`, `destination_id C1.id`.
4. pl(PJ, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-M").destination_label == "Machine (Press 1)"`.
2. returns: `row("PO-J").destination_label == "Project · Main Build / Roof"`.

### IOS-P-11 — the smallest positive total is shown
- **Rules:** `_purchase_rows` R6, R8 (positive side)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "1.00", "0.01").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").line_total == Decimal("0.01")`.
2. returns: `row("PO-1").unit_price == Decimal("0.01")`.

### IOS-P-12 — POs of the lower and higher workspace are not listed
- **Rules:** `get_orders_for_item` R10; `_purchase_rows` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po("PO-Z").
2. pl(P0, I1, "1.00", "5.00").
3. P0B = W0 po("PO-ZB").
4. pl(P0B, I0, "1.00", "5.00").
5. P1 = po("PO-1").
6. pl(P1, I1, "1.00", "5.00").
7. P9 = W2 po("PO-N").
8. pl(P9, I1, "1.00", "5.00").
9. P9B = W2 po("PO-NB").
10. pl(P9B, I9, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-P-13 — a PO with another workspace's account is left out
- **Rules:** `_purchase_rows` R10 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 3, names "Zero Co", "Far Co" shown)

**Given**
1. PA = po("PO-A") but `account_id AC0.id`.
2. pl(PA, I1, "1.00", "5.00").
3. P1 = po("PO-1").
4. pl(P1, I1, "1.00", "5.00").
5. PB = po("PO-B") but `account_id AC9.id`.
6. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-P-14 — a PO with another workspace's status is left out
- **Rules:** `_purchase_rows` R10 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 3)

**Given**
1. PA = po("PO-A") but `current_status_id S0.id`.
2. pl(PA, I1, "1.00", "5.00").
3. P1 = po("PO-1").
4. pl(P1, I1, "1.00", "5.00").
5. PB = po("PO-B") but `current_status_id S9.id`.
6. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-P-15 — a PO stored at another workspace's factory is left out
- **Rules:** `_purchase_rows` R10 [BUG-2555]; `_build_po_destination_labels` R7
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 3, label "Storage")

**Given**
1. PA = po("PO-A") but `destination_id F0.id`.
2. pl(PA, I1, "1.00", "5.00").
3. P1 = po("PO-1").
4. pl(P1, I1, "1.00", "5.00").
5. PB = po("PO-B") but `destination_id F9.id`.
6. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-P-16 — a PO for another workspace's machine is left out
- **Rules:** `_purchase_rows` R10 [BUG-2555]; `_build_po_destination_labels` R7
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 2, label "Machine #<id>")

**Given**
1. PA = po("PO-A") but `destination_type "machine"`, `destination_id M0.id`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `destination_type "machine"`, `destination_id M9.id`.
4. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-P-17 — a PO for another workspace's component is left out
- **Rules:** `_purchase_rows` R10 [BUG-2555]; `_build_po_destination_labels` R7
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 2, label "Component #<id>")

**Given**
1. PA = po("PO-A") but `destination_type "project"`, `destination_id C0.id`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `destination_type "project"`, `destination_id C9.id`.
4. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-P-18 — a PO for this workspace's component under another workspace's project is left out
- **Rules:** `_purchase_rows` R10 [BUG-2555]; `_build_po_destination_labels` R7
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 2, project names "Zero Build" / "Far Build" shown)

**Given**
1. CX0 = `ProjectComponent(workspace_id=W1.id, project_id=PJ0.id, name="Annex")`.
2. CX9 = `ProjectComponent(workspace_id=W1.id, project_id=PJ9.id, name="Stray")`.
3. PA = po("PO-A") but `destination_type "project"`, `destination_id CX0.id`.
4. pl(PA, I1, "1.00", "5.00").
5. PB = po("PO-B") but `destination_type "project"`, `destination_id CX9.id`.
6. pl(PB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-P-19 — the row's unit price is rounded to two places
- **Rules:** `_purchase_rows` R7 via `_weighted_unit_price` R3 [BUG-2554]
- **Kind:** bug
- **Expect:** xfail BUG-2554
- **Fails today on:** Then 2 (today `33.33333333333333333333333333`)

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "3.00", "100.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").line_total == Decimal("100.00")`.
2. returns: `str(row("PO-1").unit_price) == "33.33"`.

### IOS-P-20 — quantity and total of a repeating-price PO are exact
- **Rules:** `_purchase_rows` R5, R6, R8 (regression part of BUG-2554)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "3.00", "100.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").quantity == Decimal("3.00")`.
2. returns: `row("PO-1").line_total == Decimal("100.00")`.
3. returns: `Decimal("33.33") <= row("PO-1").unit_price < Decimal("33.34")`.

### IOS-P-21 — no order_date: the stored created_at day counts, to the last microsecond
- **Rules:** `_purchase_rows` R3; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = po("PO-A") but `order_date None`, `created_at datetime(2026, 4, 30, 23, 59, 59, 999999)`.
2. pl(PA, I1, "1.00", "5.00").
3. PB = po("PO-B") but `order_date None`, `created_at datetime(2026, 5, 1, 0, 0, 0)`.
4. pl(PB, I1, "1.00", "5.00").
5. PC = po("PO-C") but `order_date None`, `created_at datetime(2026, 5, 31, 23, 59, 59, 999999)`.
6. pl(PC, I1, "1.00", "5.00").
7. PD = po("PO-D") but `order_date None`, `created_at datetime(2026, 6, 1, 0, 0, 0)`.
8. pl(PD, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"PO-B", "PO-C"}`.
3. returns: `row("PO-B").order_date == START`, `row("PO-C").order_date == END`.

### IOS-P-22 — called directly, the helper returns a plain list of row responses
- **Rules:** `_purchase_rows` R12, R1, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "2.00", "10.00").
3. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc._purchase_rows(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `type(result) is list`, `len(result) == 1`.
2. returns: `isinstance(result[0], ItemOrderRowResponse)`.
3. returns: `result[0].order_type == "purchase_order"`, `result[0].order_number == "PO-1"`.
4. returns: `result[0].quantity == Decimal("3.00")`, `result[0].line_total == Decimal("15.00")`.
5. returns: `result[0].unit_price == Decimal("5.00")`.

### IOS-P-23 — called directly with no matching PO, the helper returns an empty list
- **Rules:** `_purchase_rows` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P2 = po("PO-2").
2. pl(P2, I2, "1.00", "5.00").

**When**
- `result = svc._purchase_rows(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result == []`, `type(result) is list`.

## `ItemOrdersService._transfer_rows` (through `get_orders_for_item`)

### IOS-T-01 — every field of a transfer row; two lines are one row
- **Rules:** `_transfer_rows` R1, R2, R3; `get_orders_for_item` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = to("TO-1") but `created_at noon(MID)`.
2. tl(T1, I1, "4.00").
3. tl(T1, I1, "1.50").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`, `len(result.items) == 1`.
2. returns: `row("TO-1").order_type == "transfer_order"`, `row("TO-1").order_id == T1.id`.
3. returns: `row("TO-1").order_date == MID`.
4. returns: `row("TO-1").quantity == Decimal("5.50")`.
5. returns: `row("TO-1").unit_price is None`, `row("TO-1").line_total is None`.
6. returns: `row("TO-1").account_name is None`, `row("TO-1").destination_label is None`.
7. returns: `row("TO-1").status_name == "Draft"`.

### IOS-T-02 — every transfer counts, whatever its status
- **Rules:** `_transfer_rows` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = to("TO-A") but `current_status_id S2.id`, `created_at noon(date(2026, 5, 11))`.
2. tl(TA, I1, "1.00").
3. TB = to("TO-B") but `created_at noon(MID)`.
4. tl(TB, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `row("TO-A").status_name == "Closed"`.
3. returns: `row("TO-B").status_name == "Draft"`.

### IOS-T-03 — the range filters on the created_at day, both edges
- **Rules:** `_transfer_rows` R2; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = to("TO-A") but `created_at noon(PRE)`.
2. tl(TA, I1, "1.00").
3. TB = to("TO-B") but `created_at noon(START)`.
4. tl(TB, I1, "1.00").
5. TC = to("TO-C") but `created_at noon(END)`.
6. tl(TC, I1, "1.00").
7. TD = to("TO-D") but `created_at noon(POST)`.
8. tl(TD, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"TO-B", "TO-C"}`.

### IOS-T-04 — transfers without the item are not listed
- **Rules:** `_transfer_rows` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = to("TO-A").
2. tl(TA, I2, "9.00").
3. TB = to("TO-B").
4. tl(TB, I1, "2.00").
5. tl(TB, I2, "7.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`, `nums == ["TO-B"]`.
2. returns: `row("TO-B").quantity == Decimal("2.00")`.

### IOS-T-05 — transfers of the lower and higher workspace are not listed
- **Rules:** `get_orders_for_item` R10; `_transfer_rows` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T0 = W0 to("TO-Z").
2. tl(T0, I1, "1.00").
3. T1 = to("TO-1").
4. tl(T1, I1, "1.00").
5. T9 = W2 to("TO-N").
6. tl(T9, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["TO-1"]`.

### IOS-T-06 — a transfer with another workspace's status is left out
- **Rules:** `_transfer_rows` R4 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 3)

**Given**
1. TA = to("TO-A") but `current_status_id S0.id`.
2. tl(TA, I1, "1.00").
3. T1 = to("TO-1").
4. tl(T1, I1, "1.00").
5. TB = to("TO-B") but `current_status_id S9.id`.
6. tl(TB, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["TO-1"]`.

### IOS-T-07 — called directly, the helper returns row responses with the empty fields None
- **Rules:** `_purchase_rows` R12 (shape shared by all four helpers); `_transfer_rows` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = to("TO-1").
2. tl(T1, I1, "4.00").

**When**
- `result = svc._transfer_rows(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `type(result) is list`, `len(result) == 1`.
2. returns: `isinstance(result[0], ItemOrderRowResponse)`.
3. returns: `result[0].order_type == "transfer_order"`, `result[0].quantity == Decimal("4.00")`.
4. returns: `result[0].unit_price is None`, `result[0].line_total is None`.

### IOS-T-08 — the stored created_at day counts, to the last microsecond
- **Rules:** `_transfer_rows` R2; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = to("TO-A") but `created_at datetime(2026, 4, 30, 23, 59, 59, 999999)`.
2. tl(TA, I1, "1.00").
3. TB = to("TO-B") but `created_at datetime(2026, 5, 1, 0, 0, 0)`.
4. tl(TB, I1, "1.00").
5. TC = to("TO-C") but `created_at datetime(2026, 5, 31, 23, 59, 59, 999999)`.
6. tl(TC, I1, "1.00").
7. TD = to("TO-D") but `created_at datetime(2026, 6, 1, 0, 0, 0)`.
8. tl(TD, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="transfer_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"TO-B", "TO-C"}`.
3. returns: `row("TO-B").order_date == START`, `row("TO-C").order_date == END`.

## `ItemOrdersService._sales_rows` (through `get_orders_for_item`)

### IOS-S-01 — every field of a sales row
- **Rules:** `_sales_rows` R1, R2, R3, R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = so("SO-1") but `order_date MID`.
2. sl(S1, I1, "3.00", "300.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`, `len(result.items) == 1`.
2. returns: `row("SO-1").order_type == "sales_order"`, `row("SO-1").order_id == S1.id`.
3. returns: `row("SO-1").order_date == MID`.
4. returns: `row("SO-1").quantity == Decimal("3.00")`.
5. returns: `row("SO-1").unit_price == Decimal("100.00")`.
6. returns: `row("SO-1").line_total == Decimal("300.00")`.
7. returns: `row("SO-1").account_name == "Acme"`, `row("SO-1").status_name == "Draft"`.
8. returns: `row("SO-1").destination_label is None`.

### IOS-S-02 — free-text and other-item lines never match
- **Rules:** `_sales_rows` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. SA = so("SO-A").
2. sl(SA, None, "5.00", "50.00").
3. sl(SA, I2, "2.00", "20.00").
4. SB = so("SO-B").
5. sl(SB, I1, "2.00", "40.00").
6. sl(SB, None, "9.00", "90.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`, `nums == ["SO-B"]`.
2. returns: `row("SO-B").quantity == Decimal("2.00")`.
3. returns: `row("SO-B").line_total == Decimal("40.00")`.

### IOS-S-03 — any status counts
- **Rules:** `_sales_rows` R1, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. SA = so("SO-A") but `current_status_id S2.id`, `order_date date(2026, 5, 11)`.
2. sl(SA, I1, "1.00", "5.00").
3. SB = so("SO-B").
4. sl(SB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `row("SO-A").status_name == "Closed"`.

### IOS-S-04 — order_date range, both edges
- **Rules:** `_sales_rows` R2; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SA = so("SO-A") but `order_date PRE`, `created_at noon(START)`.
2. sl(SA, I1, "1.00", "5.00").
3. SB = so("SO-B") but `order_date START`, `created_at noon(PRE)`.
4. sl(SB, I1, "1.00", "5.00").
5. SC = so("SO-C") but `order_date END`, `created_at noon(POST)`.
6. sl(SC, I1, "1.00", "5.00").
7. SD = so("SO-D") but `order_date POST`, `created_at noon(END)`.
8. sl(SD, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"SO-B", "SO-C"}`.

### IOS-S-05 — two lines: one row, summed and weighted
- **Rules:** `_sales_rows` R3, R4; `get_orders_for_item` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = so("SO-1").
2. sl(S1, I1, "1.00", "10.00").
3. sl(S1, I1, "3.00", "30.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `row("SO-1").quantity == Decimal("4.00")`.
3. returns: `row("SO-1").line_total == Decimal("40.00")`.
4. returns: `row("SO-1").unit_price == Decimal("10.00")`.

### IOS-S-06 — sales orders of the lower and higher workspace are not listed
- **Rules:** `get_orders_for_item` R10; `_sales_rows` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = W0 so("SO-Z").
2. sl(S0, I1, "1.00", "5.00").
3. S1 = so("SO-1").
4. sl(S1, I1, "1.00", "5.00").
5. S9 = W2 so("SO-N").
6. sl(S9, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["SO-1"]`.

### IOS-S-07 — a sales order with another workspace's account is left out
- **Rules:** `_sales_rows` R6 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 3)

**Given**
1. SA = so("SO-A") but `account_id AC0.id`.
2. sl(SA, I1, "1.00", "5.00").
3. S1 = so("SO-1").
4. sl(S1, I1, "1.00", "5.00").
5. SB = so("SO-B") but `account_id AC9.id`.
6. sl(SB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["SO-1"]`.

### IOS-S-08 — a sales order with another workspace's status is left out
- **Rules:** `_sales_rows` R6 [BUG-2555]
- **Kind:** bug
- **Expect:** xfail BUG-2555
- **Fails today on:** Then 1 (today total 3)

**Given**
1. SA = so("SO-A") but `current_status_id S0.id`.
2. sl(SA, I1, "1.00", "5.00").
3. S1 = so("SO-1").
4. sl(S1, I1, "1.00", "5.00").
5. SB = so("SO-B") but `current_status_id S9.id`.
6. sl(SB, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["SO-1"]`.

### IOS-S-09 — a half cent unit price rounds up
- **Rules:** `_sales_rows` R4 via `_weighted_unit_price` R3 [BUG-2554]
- **Kind:** bug
- **Expect:** xfail BUG-2554
- **Fails today on:** Then 2 (today `0.125`)

**Given**
1. S1 = so("SO-1").
2. sl(S1, I1, "2.00", "0.25").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `row("SO-1").line_total == Decimal("0.25")`.
2. returns: `str(row("SO-1").unit_price) == "0.13"`.

### IOS-S-10 — quantity and total of a half-cent order are exact
- **Rules:** `_sales_rows` R3, R4 (regression part of BUG-2554)
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = so("SO-1").
2. sl(S1, I1, "2.00", "0.25").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `row("SO-1").quantity == Decimal("2.00")`.
2. returns: `row("SO-1").line_total == Decimal("0.25")`.
3. returns: `Decimal("0.12") <= row("SO-1").unit_price <= Decimal("0.13")`.

### IOS-S-11 — called directly, the helper returns row responses with no destination
- **Rules:** `_purchase_rows` R12 (shape shared by all four helpers); `_sales_rows` R3, R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = so("SO-1").
2. sl(S1, I1, "2.00", "50.00").

**When**
- `result = svc._sales_rows(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `type(result) is list`, `len(result) == 1`.
2. returns: `isinstance(result[0], ItemOrderRowResponse)`.
3. returns: `result[0].order_type == "sales_order"`, `base(result[0].order_number) == "SO-1"`.
4. returns: `result[0].unit_price == Decimal("25.00")`, `result[0].line_total == Decimal("50.00")`.
5. returns: `result[0].destination_label is None`.

## `ItemOrdersService._work_rows` (through `get_orders_for_item`)

### IOS-W-01 — a work order with only a deleted line of the item is not listed
- **Rules:** `_work_rows` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. WO1 = wo("WO-1").
2. wl(WO1, I1, "5.00") but `is_deleted True`.
3. wl(WO1, I2, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-W-02 — no type: a deleted work line does not bring its order in
- **Rules:** `_work_rows` R1; `get_orders_for_item` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "1.00", "5.00").
3. WO1 = wo("WO-1").
4. wl(WO1, I1, "5.00") but `is_deleted True`.

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-W-03 — every field of a work row; deleted lines not counted
- **Rules:** `_work_rows` R1, R4, R5 [BUG-2550]; `get_orders_for_item` R11
- **Kind:** bug
- **Expect:** xfail BUG-2550
- **Fails today on:** Then 1 (the call raises AttributeError: status read as an enum)

**Given**
1. WO1 = wo("WO-1") but `created_at noon(MID)`.
2. wl(WO1, I1, "2.00").
3. wl(WO1, I1, "3.00").
4. wl(WO1, I1, "10.00") but `is_deleted True`.

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`, `len(result.items) == 1`.
2. returns: `row("WO-1").order_type == "work_order"`, `row("WO-1").order_id == WO1.id`.
3. returns: `row("WO-1").order_date == MID`.
4. returns: `row("WO-1").quantity == Decimal("5.00")`.
5. returns: `row("WO-1").status_name == "DRAFT"`.
6. returns: `row("WO-1").unit_price is None`, `row("WO-1").line_total is None`.
7. returns: `row("WO-1").account_name is None`, `row("WO-1").destination_label is None`.

### IOS-W-04 — in-progress and completed work orders show their status text
- **Rules:** `_work_rows` R2 (kept states), R5 [BUG-2550]
- **Kind:** bug
- **Expect:** xfail BUG-2550
- **Fails today on:** Then 1 (the call raises AttributeError: status read as an enum)

**Given**
1. WA = wo("WO-A") but `status "IN_PROGRESS"`, `created_at noon(date(2026, 5, 11))`.
2. wl(WA, I1, "1.00").
3. WB = wo("WO-B") but `status "COMPLETED"`, `created_at noon(MID)`.
4. wl(WB, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `row("WO-A").status_name == "IN_PROGRESS"`.
3. returns: `row("WO-B").status_name == "COMPLETED"`.

### IOS-W-05 — a voided work order is left out
- **Rules:** `_work_rows` R2 [BUG-2552]
- **Kind:** bug
- **Expect:** xfail BUG-2552
- **Fails today on:** Then 1 (the call raises AttributeError: the voided order is listed and its status read as an enum)

**Given**
1. WV = wo("WO-V") but `status "VOIDED"`.
2. wl(WV, I1, "50.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-W-06 — a deleted work order with live lines is left out
- **Rules:** `_work_rows` R3 [BUG-2553]
- **Kind:** bug
- **Expect:** xfail BUG-2553
- **Fails today on:** Then 1 (the call raises AttributeError: the deleted order is listed and its status read as an enum)

**Given**
1. WD = deleted wo("WO-D").
2. wl(WD, I1, "4.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-W-07 — work orders on the days just outside the range are not listed
- **Rules:** `_work_rows` R4; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WA = wo("WO-A") but `created_at noon(PRE)`.
2. wl(WA, I1, "1.00").
3. WD = wo("WO-D") but `created_at noon(POST)`.
4. wl(WD, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### IOS-W-08 — work orders on the first and last day are listed
- **Rules:** `_work_rows` R4, R5 [BUG-2550]; `get_orders_for_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2550
- **Fails today on:** Then 1 (the call raises AttributeError: status read as an enum)

**Given**
1. WA = wo("WO-A") but `created_at noon(PRE)`.
2. wl(WA, I1, "1.00").
3. WB = wo("WO-B") but `created_at noon(START)`.
4. wl(WB, I1, "1.00").
5. WC = wo("WO-C") but `created_at noon(END)`.
6. wl(WC, I1, "1.00").
7. WD = wo("WO-D") but `created_at noon(POST)`.
8. wl(WD, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `numset == {"WO-B", "WO-C"}`.

### IOS-W-09 — work orders of the lower and higher workspace are not listed
- **Rules:** `get_orders_for_item` R10; `_work_rows` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. WZ = W0 wo("WO-Z").
2. wl(WZ, I1, "1.00").
3. WN = W2 wo("WO-N").
4. wl(WN, I1, "1.00").
5. P1 = po("PO-1").
6. pl(P1, I1, "1.00", "5.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `nums == ["PO-1"]`.

### IOS-W-10 — called directly with only a deleted line, the helper returns an empty list
- **Rules:** `_purchase_rows` R12 (shape shared by all four helpers); `_work_rows` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WO1 = wo("WO-1").
2. wl(WO1, I1, "5.00") but `is_deleted True`.

**When**
- `result = svc._work_rows(db, workspace_id=W1.id, item_id=I1.id, from_date=None, to_date=None)`.

**Then**
1. returns: `result == []`, `type(result) is list`.

### IOS-W-11 — work orders a microsecond before the range and at midnight after it are not listed
- **Rules:** `_work_rows` R4; `get_orders_for_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WA = wo("WO-A") but `created_at datetime(2026, 4, 30, 23, 59, 59, 999999)`.
2. wl(WA, I1, "1.00").
3. WD = wo("WO-D") but `created_at datetime(2026, 6, 1, 0, 0, 0)`.
4. wl(WD, I1, "1.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="work_order", from_date=START, to_date=END, limit=1000)`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

## Priced quantity and zero totals — BUG-2490, BUG-2491 (OQ-33 answered)

Owner answer 2026-11-10 (OQ-33): the unit price is the priced subtotal over the **priced** quantity, rounded half up (BUG-2490, with BUG-2554); when at least one line of the item is priced the line total is the priced sum, 0.00 included, and both are `None` only when no line is priced (BUG-2491). Partly priced, zero-priced and unpriced orders appear only in this section.

### IOS-OQ33-01 — a partly priced PO divides by the priced quantity only
- **Rules:** `_purchase_rows` R7 [BUG-2490]
- **Kind:** bug
- **Expect:** xfail BUG-2490, BUG-2554 (passes only when both are fixed)
- **Fails today on:** Then 2 (today the priced total is spread over all 20: `2.5`)

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "10.00", "50.00").
3. pl(P1, I1, "10.00", None).

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").quantity == Decimal("20.00")`.
2. returns: `row("PO-1").unit_price == Decimal("5.00")`.
3. returns: `str(row("PO-1").unit_price) == "5.00"`.
4. returns: `row("PO-1").line_total == Decimal("50.00")`.

### IOS-OQ33-02 — a PO priced at 0.00 shows line total 0.00 and unit price 0.00
- **Rules:** `_purchase_rows` R8a [BUG-2491], R7
- **Kind:** bug
- **Expect:** xfail BUG-2491, BUG-2554 (passes only when both are fixed)
- **Fails today on:** Then 2 (today a total of 0 gives `line_total None`)

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "4.00", "0.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").unit_price == Decimal("0.00")`.
2. returns: `row("PO-1").line_total == Decimal("0.00")`.
3. returns: `str(row("PO-1").line_total) == "0.00"`.
4. returns: `str(row("PO-1").unit_price) == "0.00"`.

### IOS-OQ33-03 — a wholly unpriced PO shows no unit price
- **Rules:** `_purchase_rows` R7 [BUG-2490], R8a
- **Kind:** bug
- **Expect:** xfail BUG-2490
- **Fails today on:** Then 3 (today the unit price is `0`, not `None`)

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "5.00", None).

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").quantity == Decimal("5.00")`.
2. returns: `row("PO-1").line_total is None`.
3. returns: `row("PO-1").unit_price is None`.

### IOS-OQ33-04 — quantity 0 and no price: both empty
- **Rules:** `_purchase_rows` R7a, R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "0.00", None).

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `row("PO-1").unit_price is None`.
3. returns: `row("PO-1").line_total is None`.

### IOS-OQ33-05 — a sales order priced at 0.00 shows line total 0.00 and unit price 0.00
- **Rules:** `_sales_rows` R5a [BUG-2491], R4
- **Kind:** bug
- **Expect:** xfail BUG-2491
- **Fails today on:** Then 2 (today a total of 0 gives `line_total None`)

**Given**
1. S1 = so("SO-1").
2. sl(S1, I1, "2.00", "0.00").

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="sales_order", limit=1000)`.

**Then**
1. returns: `row("SO-1").unit_price == Decimal("0.00")`.
2. returns: `row("SO-1").line_total == Decimal("0.00")`.
3. returns: `str(row("SO-1").line_total) == "0.00"`.

### IOS-OQ33-06 — a partly priced PO: quantity counts every line, line total the priced ones
- **Rules:** `_purchase_rows` R5, R6, R8 (the part of BUG-2490 that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "10.00", "50.00").
3. pl(P1, I1, "10.00", None).

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `row("PO-1").quantity == Decimal("20.00")`.
3. returns: `row("PO-1").line_total == Decimal("50.00")`.
4. returns: `str(row("PO-1").line_total) == "50.00"`.

### IOS-OQ33-07 — a half cent over the priced quantity rounds up, not to even
- **Rules:** `_purchase_rows` R7 [BUG-2490]; `_weighted_unit_price` R3 [BUG-2554]
- **Kind:** bug
- **Expect:** xfail BUG-2490, BUG-2554 (passes only when both are fixed)
- **Fails today on:** Then 2 (today `0.25` is divided by all 7, unrounded)

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "2.00", "0.25").
3. pl(P1, I1, "5.00", None).

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").quantity == Decimal("7.00")`.
2. returns: `row("PO-1").unit_price == Decimal("0.13")`.
3. returns: `str(row("PO-1").unit_price) == "0.13"`.
4. returns: `row("PO-1").line_total == Decimal("0.25")`.

### IOS-OQ33-08 — a wholly unpriced PO: quantity shown, no line total
- **Rules:** `_purchase_rows` R5, R6, R8a (the part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "5.00", None).

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `row("PO-1").quantity == Decimal("5.00")`.
3. returns: `row("PO-1").line_total is None`.

### IOS-OQ33-09 — a priced line of quantity 0 next to an unpriced one: no unit price, total 0.00
- **Rules:** `_purchase_rows` R7 [BUG-2490] (priced quantity 0 → `None`), R8a
- **Kind:** bug
- **Expect:** xfail BUG-2490, BUG-2491 (passes only when both are fixed)
- **Fails today on:** Then 2 (today `0.00 / 5` gives unit price `0`)

**Given**
1. P1 = po("PO-1").
2. pl(P1, I1, "0.00", "0.00").
3. pl(P1, I1, "5.00", None).

**When**
- `result = svc.get_orders_for_item(db, workspace_id=W1.id, item_id=I1.id, order_type="purchase_order", limit=1000)`.

**Then**
1. returns: `row("PO-1").quantity == Decimal("5.00")`.
2. returns: `row("PO-1").unit_price is None`.
3. returns: `row("PO-1").line_total == Decimal("0.00")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_orders_for_item` R4a [BUG-2556] | `GET /items/{item_id}/orders/` (endpoint or its query model) | only `from_date` or only `to_date` → 422, nothing returned; both or neither → accepted |

## Spec gaps
None. Gaps 1–4 of revision 1 were closed in spec round 2 (Gap log G1–G4: row-helper return shape `_purchase_rows` R12; naive `created_at`, stored day, Facts "Date columns"; Python sort key `get_orders_for_item` R13; Facts "Minimum rows").

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_dec` | R1 | DC-01 |
| `_dec` | R2 | DC-02, DC-03 |
| `_dec` | R3 / Errors | DC-04 |
| `_in_date_range` | R1 | DR-01, DR-02 (and every date card) |
| `_weighted_unit_price` | R1 | WP-01, WP-02, WP-03 |
| `_weighted_unit_price` | R2 | WP-03, WP-04, WP-05, WP-06 |
| `_weighted_unit_price` | R3 [BUG-2554] | WP-07, WP-08, WP-09, P-19, S-09 (regression WP-06, P-20, S-10) |
| `_build_po_destination_labels` | R1 | DL-01, DL-02, P-09 |
| `_build_po_destination_labels` | R2 | DL-02, DL-03, P-01 |
| `_build_po_destination_labels` | R3 | DL-04, P-10 |
| `_build_po_destination_labels` | R4 | DL-05, P-10 |
| `_build_po_destination_labels` | R5 | DL-06 |
| `_build_po_destination_labels` | R6 | DL-07, DL-08, DL-09 |
| `_build_po_destination_labels` | R7 [BUG-2555] | DL-11, DL-12, DL-13, DL-14 (regression DL-07, DL-10) |
| `get_orders_for_item` | R1 / Errors row 1 | G-01, G-02, G-03 |
| `get_orders_for_item` | R2 | G-04 |
| `get_orders_for_item` | R3 | G-05, G-06, G-07, G-08, G-09, G-10, W-02 |
| `get_orders_for_item` | R4 | G-11, G-12, P-05, P-06, P-21, T-03, T-08, S-04, W-07, W-08, W-11 |
| `get_orders_for_item` | R4a [BUG-2556] | G-13, G-14 (service part); endpoint deferred |
| `get_orders_for_item` | R5 | G-15, G-16, G-17, G-18 |
| `get_orders_for_item` | R6 | G-19 |
| `get_orders_for_item` | R6 [BUG-2551] | G-20, G-35 (pass, type key), G-21, G-22, G-36 (non-strict), G-37 (strict), G-23 |
| `get_orders_for_item` | R13 | G-20, G-21, G-22, G-35, G-36, G-37 |
| `get_orders_for_item` | R7 | G-24, G-27, G-30, G-31 |
| `get_orders_for_item` | R8 | G-22, G-24, G-25, G-26, G-27, G-28, G-29, G-30, G-31 |
| `get_orders_for_item` | R9 | G-11, G-32 |
| `get_orders_for_item` | R10 | G-31, P-12, T-05, S-06, W-09 |
| `get_orders_for_item` | R11 | G-33, T-01, S-05, W-03 |
| `get_orders_for_item` | R12 | G-34, G-01 (exception unchanged) |
| `get_orders_for_item` | Errors row 2 (AttributeError today) | G-06, G-10, G-23, W-03, W-04, W-08 |
| `_purchase_rows` | R1 | P-01, P-02, G-32, P-12 |
| `_purchase_rows` | R2 | P-03, G-30 |
| `_purchase_rows` | R3 | P-04, P-05, P-06, P-21 |
| `_purchase_rows` | R4 | G-15, G-16, G-17 |
| `_purchase_rows` | R5 | P-01, P-02, P-07, G-33, P-20, P-22, OQ33-06, OQ33-08 |
| `_purchase_rows` | R6 | P-01, P-02, P-11, G-33, P-22, OQ33-06, OQ33-08 |
| `_purchase_rows` | R7 [BUG-2490] | OQ33-01, OQ33-03, OQ33-07, OQ33-09 (fully priced P-01, P-22) |
| `_purchase_rows` | R7a | OQ33-04, P-19 (rounding, BUG-2554), P-20 |
| `_purchase_rows` | R8 | P-01, P-11, P-20, OQ33-06 |
| `_purchase_rows` | R8a [BUG-2491] | OQ33-02, OQ33-09 (both-empty side OQ33-04, OQ33-08) |
| `_purchase_rows` | R9 | P-01, P-08, P-09, P-10 |
| `_purchase_rows` | R10 [BUG-2555] | P-13, P-14, P-15, P-16, P-17, P-18 |
| `_purchase_rows` | R11 | no card (no order to check; ordering is `get_orders_for_item` R6, R13) |
| `_purchase_rows` | R12 | P-22, P-23, T-07, S-11, W-10 |
| `_transfer_rows` | R1 | T-01, T-02, T-04, T-05 |
| `_transfer_rows` | R2 | T-01, T-03, T-08 |
| `_transfer_rows` | R3 | T-01, T-02, T-04, T-07 |
| `_transfer_rows` | R4 [BUG-2555] | T-06 |
| `_sales_rows` | R1 | S-01, S-02, S-03, S-06 |
| `_sales_rows` | R2 | S-01, S-04 (fallback unreachable: `order_date` NOT NULL) |
| `_sales_rows` | R3 | S-01, S-02, S-05, S-10, S-11 |
| `_sales_rows` | R4 | S-01, S-05, S-09, S-11, OQ33-05 |
| `_sales_rows` | R5 | S-01, S-05, S-11 |
| `_sales_rows` | R5a [BUG-2491] | OQ33-05 |
| `_sales_rows` | R6 | S-01, S-03, S-11 |
| `_sales_rows` | R6 [BUG-2555] | S-07, S-08 |
| `_work_rows` | R1 | W-01, W-02, W-03, W-09, W-10 |
| `_work_rows` | R2 [BUG-2552] | W-05 (kept states W-04) |
| `_work_rows` | R3 [BUG-2553] | W-06 |
| `_work_rows` | R4 | W-03, W-07, W-08, W-11 |
| `_work_rows` | R5 [BUG-2550] | G-06, G-10, G-23, W-03, W-04, W-08 |
