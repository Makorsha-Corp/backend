# Test cases — `app/services/purchase_order_item_insights_service.py`

> **Spec:** `tests/unit/services/purchase_order_item_insights_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Note (2026-11-10, after revision 4):** wording only — the Deferred row for `_pick_avg_supplier_lowest` R7 now says weights are always > 0 (spec R7), not ≥ 1; A-14 uses a 0.50 weight. No card changed; counts unchanged.
> **Revision:** 4 (2026-11-10) — `purchase_order_item_insights_service.verify.md` F1 (survivors #51, #52): new A-12 (the cheaper supplier listed first stays the winner against a pricier one with more orders), A-13 (equal average: the first supplier, with more orders, is not replaced by a later one with fewer). F2 (survivor #68): new A-14 (quantity 0.50 weighs 0.50, not 1). F3 (survivor #18): new DC-01 (setting a field of a `_HistoryLine` raises `FrozenInstanceError`, spec Not specified / G1). No card changed or retired.
> **Revision:** 3 (2026-11-10) — Parallel runs note added to Conventions (this module builds only purchase orders, whose numbers are unique per workspace; no suffix needed). No card changed, added or retired.
> **Revision:** 2 (2026-11-10) — spec round 2, Gap log G1–G2 closed. G1: `_HistoryLine` is the spec's frozen dataclass with exactly the nine fields HL already passes (no change to HL). G2: the void columns are the spec's own (Externals; the voided-po builder already writes them); the post-BUG-2542 clock is the module's `utcnow` only, so **clock(...)** no longer patches `app.utils.time.utcnow`. No card changed, added or retired.
> **Counts:** 74 cases · 62 expected-to-pass · 12 expected-to-fail (bugs) · 1 deferred

## Reviewer summary
- **Per callable:** `_dec` 4 · `_to_ref` 2 · `get_item_price_insights` 22 (6 bug) · `_fetch_history_lines` 17 (4 bug) · `_pick_last_ordered` 6 · `_pick_min_price_ref` 8 · `_pick_avg_supplier_lowest` 14 (2 bug) · `_HistoryLine` 1.
- **Depth:** full (money references and a real ranking decision). Workspace isolation is tested with W0 and W2 rows on both sides of W1 (items, accounts, POs, lines); each HR-16 shape (foreign line, foreign supplier from W0 and from W2, foreign item on the viewed PO) is its own card. Window edges: today, today+1, today−30, today−31, today−90, today−91.
- **Expected-to-fail:** BUG-2540 6 (F-09, F-10, F-13, F-14, G-15, G-16), BUG-2541 3 (G-12, G-13, G-14), BUG-2542 1 (G-22), BUG-2543 2 (A-10, A-11). All strict. Regression parts that hold today are pass cards: F-11, F-15 (the line itself still returned), G-11 (the W1 item's row still there).
- **Notable design choices:**
  - The pickers are tested directly with hand-made `_HistoryLine`s (spec note), so tie keys and helper-only branches are deterministic; the public method is tested for the wiring, windows, isolation and the five references at once (G-08 makes all five point at different lines).
  - Window cards patch **both** clocks to the same day (CLOCK), so they pass before and after BUG-2542; only G-22 uses a skewed clock (SKEW). Every clock card is `Author: claude`.
  - BUG-2543 is shown at helper level with the tied lines in the order that makes today's "first seen" pick the wrong supplier; the same data in the other order would pass today, so it gets no strict card. No `ORDER BY` card: the intended fix is in the picker, not the query.
  - A-04 is built so only exact `Decimal` averages pick the right supplier (rounding to 2 places would make a tie). HR-15 does not apply: nothing is rounded or returned as computed money; prices are compared as stored, with `str()` checks for scale.
  - Voided POs carry every void column the spec's Externals list (`voided`, `void_note`, `voided_at`, `voided_by`); only `voided` is read.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `PII` = `app/services/purchase_order_item_insights_service.py`. `D` _dec · `R` _to_ref · `G` get_item_price_insights · `F` _fetch_history_lines · `L` _pick_last_ordered · `M` _pick_min_price_ref · `A` _pick_avg_supplier_lowest · `DC` the `_HistoryLine` dataclass.

**Imports.** `import app.services.purchase_order_item_insights_service as mod`; `from app.services.purchase_order_item_insights_service import purchase_order_item_insights_service, _dec, _to_ref, _HistoryLine`; `ItemPriceInsightRef` (`app.schemas.purchase_order_item_insights`); models `PurchaseOrder`, `PurchaseOrderItem`, `Item`, `Account`, `Status` (`app.models.<module>`); `HTTPException` (`fastapi`); `Decimal`, `InvalidOperation` (`decimal`); `date`, `datetime`; `patch` (`unittest.mock`); `FrozenInstanceError` (`dataclasses`).

**Fixed values.** `svc` = `purchase_order_item_insights_service`. `result` = what the When returns. MISSING = `999999999`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. TODAY = `date(2026, 6, 15)`. `row` = `result.items[0]`.

**Standing rows** (every DB test, no Given line; built in this order, each flushed): W0, W1, W2 = `make_workspace(db)` (so `W0.id < W1.id < W2.id`); U1 = `make_profile(db)`; S0, S1, S9 = `Status(workspace_id=…, name="Open", comment="")` in W0, W1, W2. Items `Item(workspace_id=…, name=…, name_normalized=<name lower>, unit="pcs")`, in this order: I0 (W0, "Zero Bolt"), I1 (W1, "Bolt"), I2 (W1, "Nut"), I3 (W1, "Washer"), I9 (W2, "Far Bolt") — so `I0.id < I1.id < I2.id < I3.id < I9.id`. Accounts `Account(workspace_id=…, name=…)`, in this order: AC0 (W0, "Zero Co"), AC1 (W1, "Acme"), AC2 (W1, "Beta"), AC9 (W2, "Far Co").

**Given rows.** Built directly, flushed one at a time in the order written (ids rise in that order).
- **po** = `PurchaseOrder(workspace_id=W1.id, po_number=…, destination_type="storage", destination_id=1, current_status_id=S1.id, created_by=U1.id)`; `account_id` and `order_date` not passed unless the card names them. **W0 po** / **W2 po** = the same with `workspace_id W0.id` / `W2.id` and `current_status_id S0.id` / `S9.id`. **voided** po = `voided True`, `void_note "Void"`, `voided_at T0`, `voided_by U1.id`.
- **ln of P** = `PurchaseOrderItem(workspace_id=P.workspace_id, purchase_order_id=P.id, line_number=1, item_id=…, quantity_ordered=Decimal("1.00"), unit_price=…)`; the card gives the item and `unit_price` and any other column that differs.
- **HL(...)** = a local helper in the test: `def HL(line_id, purchase_order_id, unit_price, order_date, account_id=None, account_name=None, quantity_ordered=Decimal("1.00"), item_id=1): return _HistoryLine(item_id=item_id, line_id=line_id, purchase_order_id=purchase_order_id, po_number=f"PO-{purchase_order_id}", account_id=account_id, account_name=account_name, unit_price=unit_price, quantity_ordered=quantity_ordered, order_date=order_date)`. Helper cards need no database rows.

**Calls.** `svc.get_item_price_insights(db, po_id=…, workspace_id=…)`; `svc._fetch_history_lines(db, workspace_id=…, item_ids=[…], exclude_po_id=…)`; `svc._pick_last_ordered([...])`; `svc._pick_min_price_ref([...], from_date=…, to_date=…)` (bounds omitted unless shown); `svc._pick_avg_supplier_lowest([...])`.

**Clocks.** **clock(local, utc)** = around the When: `patch.object(mod, "date", FixedDate)` where `class FixedDate(date)` has `@classmethod today(cls): return local`; plus `patch("app.services.purchase_order_item_insights_service.utcnow", return_value=utc, create=True)` (the module's own name, read after BUG-2542; `create=True` until the fix lands). **CLOCK** = clock(`date(2026, 6, 15)`, `datetime(2026, 6, 15, 12, 0)`) (both say TODAY). **SKEW** = clock(`date(2026, 6, 16)`, `datetime(2026, 6, 15, 20, 0)`) (server local day ahead of UTC). Cards without a clock line patch nothing.

**Named checks.**
- **ids(lines)** = `{l.line_id for l in lines}`. **item_ids(result)** = `[r.item_id for r in result.items]`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **commit point** = `db.commit()` after the Given lines above it; lines marked "(after the commit point)" run after it, unflushed.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call. `session:` lines check `db` directly, before anything expires it.
- **nothing written** = the number of `purchase_orders` and `purchase_order_items` rows equals its value before the call.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`.

**Parallel runs.** Only `po_number` is built, and it is unique per workspace (every test makes fresh workspaces), so numbers are stored as written. Order, transfer and return numbers that are unique across all workspaces (BUG-726 and siblings) are not built here; a later card that builds one stores it with the per-process suffix **GN(n)** = `f"{n}-{os.getpid()}"`.

**Race simulations.** None.

## `_dec`

### PII-D-01 — None gives zero
- **Rules:** `_dec` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = _dec(None)`.

**Then**
1. returns: `result == Decimal(0)`.
2. returns: `isinstance(result, Decimal)`.

### PII-D-02 — a Decimal keeps its scale
- **Rules:** `_dec` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = _dec(Decimal("10.00"))`.

**Then**
1. returns: `str(result) == "10.00"`.

### PII-D-03 — a float goes through its text, an int stays whole
- **Rules:** `_dec` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = (_dec(1.1), _dec(3))`.

**Then**
1. returns: `str(result[0]) == "1.1"`.
2. returns: `str(result[1]) == "3"`.

### PII-D-04 — text that is not a number raises
- **Rules:** `_dec` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows.

**When**
- `_dec("abc")`.

**Then**
1. raises: `InvalidOperation`.

## `_to_ref`

### PII-R-01 — the reference copies the six fields
- **Rules:** `_to_ref` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `line = HL(line_id=7, purchase_order_id=5, unit_price=Decimal("12.50"), order_date=date(2026, 3, 4), account_id=11, account_name="Acme", quantity_ordered=Decimal("4.00"), item_id=3)`.

**When**
- `result = _to_ref(line)`.

**Then**
1. returns: `isinstance(result, ItemPriceInsightRef)`.
2. returns: `result.purchase_order_id == 5`, `result.po_number == "PO-5"`, `result.account_id == 11`, `result.account_name == "Acme"`.
3. returns: `result.unit_price == Decimal("12.50")`, `str(result.unit_price) == "12.50"`, `result.order_date == date(2026, 3, 4)`.
4. returns: `set(result.model_dump()) == {"purchase_order_id", "po_number", "account_id", "account_name", "unit_price", "order_date"}`.

### PII-R-02 — None values stay None
- **Rules:** `_to_ref` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `line = HL(line_id=7, purchase_order_id=5, unit_price=None, order_date=None)`.

**When**
- `result = _to_ref(line)`.

**Then**
1. returns: `result.account_id is None`, `result.account_name is None`.
2. returns: `result.unit_price is None`, `result.order_date is None`.

## `get_item_price_insights`

### PII-G-01 — an unknown PO id is 404 and nothing changes
- **Rules:** `get_item_price_insights` R1, R7; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. commit point.

**When**
- with spies: `svc.get_item_price_insights(db, po_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == "Purchase order with ID 999999999 not found"`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. nothing written: row counts unchanged.

### PII-G-02 — a PO of a later workspace is 404
- **Rules:** `get_item_price_insights` R1; Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. P9 = W2 po `po_number "PO-9"`.
3. ln of P9: item I9, `unit_price Decimal("5.00")`.

**When**
- `svc.get_item_price_insights(db, po_id=P9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Purchase order with ID {P9.id} not found"`.
2. nothing written: row counts unchanged.

### PII-G-03 — a PO of an earlier workspace is 404
- **Rules:** `get_item_price_insights` R1; Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po `po_number "PO-0"`.
2. ln of P0: item I0, `unit_price Decimal("5.00")`.
3. P1 = po `po_number "PO-1"`.

**When**
- `svc.get_item_price_insights(db, po_id=P0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Purchase order with ID {P0.id} not found"`.
2. nothing written: row counts unchanged.

### PII-G-04 — a voided PO is answered
- **Rules:** `get_item_price_insights` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PV = voided po `po_number "PO-V"`.
2. ln of PV: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc.get_item_price_insights(db, po_id=PV.id, workspace_id=W1.id)`.

**Then**
1. returns: `item_ids(result) == [I1.id]`.
2. returns: `row.last_ordered is None`, `row.lowest.all_time is None`.

### PII-G-05 — a PO with no lines gives no rows
- **Rules:** `get_item_price_insights` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. P2 = po `po_number "PO-2"`.
3. ln of P2: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.items == []`.

### PII-G-06 — a line with a later workspace's workspace_id is not seen
- **Rules:** `get_item_price_insights` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. ln of P1: item I1, `unit_price Decimal("5.00")`, but `workspace_id W2.id`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.items == []`.

### PII-G-07 — a line with an earlier workspace's workspace_id is not seen
- **Rules:** `get_item_price_insights` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. ln of P1: item I2, `unit_price Decimal("5.00")`, but `workspace_id W0.id`.
3. ln of P1: item I3, `unit_price Decimal("6.00")`, `line_number 2`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `item_ids(result) == [I3.id]`.

### PII-G-08 — the five references each point at their own line
- **Rules:** `get_item_price_insights` R4, R5, R6; `_pick_last_ordered` R2; `_pick_min_price_ref` R1, R4; `_pick_avg_supplier_lowest` R1, R4
- **Kind:** happy
- **Expect:** pass
- **Author:** claude

**Given**
1. PC = po `po_number "PO-C"`, `account_id AC1.id`, `order_date date(2026, 6, 14)`; ln of PC: item I1, `unit_price Decimal("0.50")`.
2. H1 = po `po_number "PO-H1"`, `order_date date(2026, 1, 10)`; ln of H1: item I1, `unit_price Decimal("4.00")`.
3. H2 = po `po_number "PO-H2"`, `account_id AC1.id`, `order_date date(2026, 4, 1)`; ln of H2: item I1, `unit_price Decimal("5.00")`.
4. H3 = po `po_number "PO-H3"`, `account_id AC1.id`, `order_date date(2026, 6, 1)`; ln of H3: item I1, `unit_price Decimal("30.00")`.
5. H4 = po `po_number "PO-H4"`, `order_date date(2026, 6, 20)`; ln of H4: item I1, `unit_price None`.
6. H5 = po `po_number "PO-H5"`, `account_id AC2.id`, `order_date date(2026, 2, 1)`; ln of H5: item I1, `unit_price Decimal("7.00")`.
7. H6 = po `po_number "PO-H6"`, `order_date date(2026, 6, 10)`; ln of H6: item I1, `unit_price Decimal("12.00")`.

**When**
- under CLOCK: `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `item_ids(result) == [I1.id]`.
2. returns: `row.last_ordered.purchase_order_id == H4.id`, `row.last_ordered.unit_price is None`, `row.last_ordered.order_date == date(2026, 6, 20)`.
3. returns: `row.lowest.avg_supplier.purchase_order_id == H5.id`, `row.lowest.avg_supplier.account_id == AC2.id`, `row.lowest.avg_supplier.account_name == "Beta"`.
4. returns: `row.lowest.all_time.purchase_order_id == H1.id`, `row.lowest.all_time.unit_price == Decimal("4.00")`, `row.lowest.all_time.account_id is None`.
5. returns: `row.lowest.days_30.purchase_order_id == H6.id`, `row.lowest.days_30.po_number == "PO-H6"`, `row.lowest.days_30.unit_price == Decimal("12.00")`.
6. returns: `row.lowest.days_90.purchase_order_id == H2.id`, `row.lowest.days_90.account_name == "Acme"`, `str(row.lowest.days_90.unit_price) == "5.00"`, `row.lowest.days_90.order_date == date(2026, 4, 1)`.

### PII-G-09 — an item with no history has all five empty
- **Rules:** `get_item_price_insights` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`; ln of P1: item I2, `unit_price Decimal("5.00")`.
2. P2 = po `po_number "PO-2"`; ln of P2: item I1, `unit_price Decimal("3.00")`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `item_ids(result) == [I2.id]`.
2. returns: `row.last_ordered is None`, `row.lowest.avg_supplier is None`, `row.lowest.all_time is None`.
3. returns: `row.lowest.days_30 is None`, `row.lowest.days_90 is None`.

### PII-G-10 — one row per item, in item_id order
- **Rules:** `get_item_price_insights` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. ln of P1: item I3, `unit_price Decimal("5.00")`, `line_number 1`.
3. ln of P1: item I1, `unit_price Decimal("6.00")`, `line_number 2`.
4. ln of P1: item I1, `unit_price Decimal("7.00")`, `line_number 3`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `item_ids(result) == [I1.id, I3.id]`.

### PII-G-11 — the W1 item keeps its row next to a foreign item
- **Rules:** `get_item_price_insights` R3, R3a (regression part)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. ln of P1: item I9, `unit_price Decimal("5.00")`, `line_number 1`.
3. ln of P1: item I1, `unit_price Decimal("6.00")`, `line_number 2`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `I1.id in item_ids(result)`.

### PII-G-12 — a later workspace's item on the PO gives no row
- **Rules:** `get_item_price_insights` R3a [BUG-2541]
- **Kind:** bug
- **Expect:** xfail BUG-2541
- **Fails today on:** Then 2 (I9 gets a row)

**Given**
1. P1 = po `po_number "PO-1"`.
2. ln of P1: item I9, `unit_price Decimal("5.00")`, `line_number 1`.
3. ln of P1: item I1, `unit_price Decimal("6.00")`, `line_number 2`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `I1.id in item_ids(result)`.
2. returns: `item_ids(result) == [I1.id]`.

### PII-G-13 — an earlier workspace's item on the PO gives no row
- **Rules:** `get_item_price_insights` R3a [BUG-2541]
- **Kind:** bug
- **Expect:** xfail BUG-2541
- **Fails today on:** Then 2 (I0 gets a row)

**Given**
1. P1 = po `po_number "PO-1"`.
2. ln of P1: item I1, `unit_price Decimal("6.00")`, `line_number 1`.
3. ln of P1: item I0, `unit_price Decimal("5.00")`, `line_number 2`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `I1.id in item_ids(result)`.
2. returns: `item_ids(result) == [I1.id]`.

### PII-G-14 — a PO holding only a foreign item gives no rows
- **Rules:** `get_item_price_insights` R3a [BUG-2541]
- **Kind:** bug
- **Expect:** xfail BUG-2541
- **Fails today on:** Then 1 (I9 gets a row)

**Given**
1. P1 = po `po_number "PO-1"`.
2. ln of P1: item I9, `unit_price Decimal("5.00")`.

**When**
- `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.items == []`.

### PII-G-15 — a later workspace's supplier never wins the lowest average
- **Rules:** `get_item_price_insights` R4; `_fetch_history_lines` R4a [BUG-2540]
- **Kind:** bug
- **Expect:** xfail BUG-2540
- **Fails today on:** Then 3 (AC9 wins at 1.00)

**Given**
1. PC = po `po_number "PO-C"`; ln of PC: item I1, `unit_price Decimal("9.00")`.
2. HX = po `po_number "PO-X"`, `account_id AC9.id`, `order_date date(2026, 1, 5)`; ln of HX: item I1, `unit_price Decimal("1.00")`.
3. HA = po `po_number "PO-A"`, `account_id AC1.id`, `order_date date(2026, 1, 6)`; ln of HA: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `row.lowest.all_time.purchase_order_id == HX.id`.
2. returns: `row.last_ordered.purchase_order_id == HA.id`.
3. returns: `row.lowest.avg_supplier.account_id == AC1.id`, `row.lowest.avg_supplier.purchase_order_id == HA.id`.
4. returns: `row.lowest.all_time.account_id is None`, `row.lowest.all_time.account_name is None`.

### PII-G-16 — an earlier workspace's supplier never wins the lowest average
- **Rules:** `get_item_price_insights` R4; `_fetch_history_lines` R4a [BUG-2540]
- **Kind:** bug
- **Expect:** xfail BUG-2540
- **Fails today on:** Then 2 (AC0 wins at 1.00)

**Given**
1. PC = po `po_number "PO-C"`; ln of PC: item I1, `unit_price Decimal("9.00")`.
2. HA = po `po_number "PO-A"`, `account_id AC1.id`, `order_date date(2026, 1, 6)`; ln of HA: item I1, `unit_price Decimal("5.00")`.
3. HX = po `po_number "PO-X"`, `account_id AC0.id`, `order_date date(2026, 1, 5)`; ln of HX: item I1, `unit_price Decimal("1.00")`.

**When**
- `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `row.lowest.all_time.purchase_order_id == HX.id`.
2. returns: `row.lowest.avg_supplier.account_id == AC1.id`, `row.lowest.avg_supplier.purchase_order_id == HA.id`.
3. returns: `row.lowest.all_time.account_name is None`.

### PII-G-17 — history of other workspaces' POs and voided POs is left out
- **Rules:** `get_item_price_insights` R5; `_fetch_history_lines` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. H0 = W0 po `po_number "PO-0"`, `order_date date(2026, 5, 3)`; ln of H0: item I1, `unit_price Decimal("1.00")`.
2. PC = po `po_number "PO-C"`; ln of PC: item I1, `unit_price Decimal("0.50")`.
3. HA = po `po_number "PO-A"`, `order_date date(2026, 5, 1)`; ln of HA: item I1, `unit_price Decimal("5.00")`.
4. HV = voided po `po_number "PO-V"`, `order_date date(2026, 5, 4)`; ln of HV: item I1, `unit_price Decimal("2.00")`.
5. H9 = W2 po `po_number "PO-9"`, `order_date date(2026, 5, 5)`; ln of H9: item I1, `unit_price Decimal("3.00")`.

**When**
- `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `row.lowest.all_time.purchase_order_id == HA.id`, `row.lowest.all_time.unit_price == Decimal("5.00")`.
2. returns: `row.last_ordered.purchase_order_id == HA.id`.

### PII-G-18 — today−30 is in the 30-day window, today−31 is not
- **Rules:** `get_item_price_insights` R6
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. PC = po `po_number "PO-C"`; ln of PC: item I1, `unit_price Decimal("9.00")`.
2. HA = po `po_number "PO-A"`, `order_date date(2026, 5, 16)`; ln of HA: item I1, `unit_price Decimal("5.00")`.
3. HB = po `po_number "PO-B"`, `order_date date(2026, 5, 15)`; ln of HB: item I1, `unit_price Decimal("1.00")`.

**When**
- under CLOCK: `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `row.lowest.days_30.purchase_order_id == HA.id`.
2. returns: `row.lowest.days_90.purchase_order_id == HB.id`.

### PII-G-19 — today is in both windows, tomorrow only in all-time
- **Rules:** `get_item_price_insights` R6; `_pick_min_price_ref` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. PC = po `po_number "PO-C"`; ln of PC: item I1, `unit_price Decimal("9.00")`.
2. HA = po `po_number "PO-A"`, `order_date date(2026, 6, 15)`; ln of HA: item I1, `unit_price Decimal("5.00")`.
3. HB = po `po_number "PO-B"`, `order_date date(2026, 6, 16)`; ln of HB: item I1, `unit_price Decimal("1.00")`.

**When**
- under CLOCK: `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `row.lowest.all_time.purchase_order_id == HB.id`.
2. returns: `row.lowest.days_30.purchase_order_id == HA.id`.
3. returns: `row.lowest.days_90.purchase_order_id == HA.id`.

### PII-G-20 — today−90 is in the 90-day window, today−91 is not
- **Rules:** `get_item_price_insights` R6
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. PC = po `po_number "PO-C"`; ln of PC: item I1, `unit_price Decimal("9.00")`.
2. HA = po `po_number "PO-A"`, `order_date date(2026, 3, 17)`; ln of HA: item I1, `unit_price Decimal("5.00")`.
3. HB = po `po_number "PO-B"`, `order_date date(2026, 3, 16)`; ln of HB: item I1, `unit_price Decimal("1.00")`.

**When**
- under CLOCK: `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `row.lowest.days_90.purchase_order_id == HA.id`.
2. returns: `row.lowest.days_30 is None`.
3. returns: `row.lowest.all_time.purchase_order_id == HB.id`.

### PII-G-21 — a read leaves pending changes pending and never commits
- **Rules:** `get_item_price_insights` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`; ln of P1: item I1, `unit_price Decimal("5.00")`.
2. P2 = po `po_number "PO-2"`.
3. commit point.
4. (after the commit point) `P2.po_number = "PO-2B"`.
5. (after the commit point) `db.add(Status(workspace_id=W1.id, name="Pending", comment=""))`, not flushed.

**When**
- with spies: `result = svc.get_item_price_insights(db, po_id=P1.id, workspace_id=W1.id)`.

**Then**
1. returns: `item_ids(result) == [I1.id]`.
2. session: `P2 in db.dirty`, `len(db.dirty) == 1`.
3. session: `len(db.new) == 1`.
4. session: `not db.deleted`.
5. mock called: `cm.call_count == 0`.
6. mock called: `rb.call_count == 0`.

### PII-G-22 — "today" is the UTC date, not the server's local date
- **Rules:** `get_item_price_insights` R6 [BUG-2542]
- **Kind:** bug
- **Expect:** xfail BUG-2542
- **Author:** claude
- **Fails today on:** Then 2 (the local-today window picks HB)

**Given**
1. PC = po `po_number "PO-C"`; ln of PC: item I1, `unit_price Decimal("9.00")`.
2. HA = po `po_number "PO-A"`, `order_date date(2026, 5, 16)`; ln of HA: item I1, `unit_price Decimal("5.00")`.
3. HB = po `po_number "PO-B"`, `order_date date(2026, 6, 16)`; ln of HB: item I1, `unit_price Decimal("3.00")`.

**When**
- under SKEW: `result = svc.get_item_price_insights(db, po_id=PC.id, workspace_id=W1.id)`.

**Then**
1. returns: `row.lowest.all_time.purchase_order_id == HB.id`.
2. returns: `row.lowest.days_30.purchase_order_id == HA.id`.
3. returns: `row.lowest.days_90.purchase_order_id == HA.id`.

## `_fetch_history_lines`

### PII-F-01 — a history line carries every field
- **Rules:** `_fetch_history_lines` R1, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`, `account_id AC1.id`, `order_date date(2026, 3, 4)`.
2. L1 = ln of P1: item I1, `unit_price Decimal("12.50")`, `quantity_ordered Decimal("3.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].line_id == L1.id`, `result[0].item_id == I1.id`, `result[0].purchase_order_id == P1.id`, `result[0].po_number == "PO-1"`.
3. returns: `result[0].account_id == AC1.id`, `result[0].account_name == "Acme"`.
4. returns: `isinstance(result[0].unit_price, Decimal)`, `str(result[0].unit_price) == "12.50"`.
5. returns: `isinstance(result[0].quantity_ordered, Decimal)`, `result[0].quantity_ordered == Decimal("3.00")`.
6. returns: `result[0].order_date == date(2026, 3, 4)`.

### PII-F-02 — lines of a voided PO are left out
- **Rules:** `_fetch_history_lines` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.
2. PV = voided po `po_number "PO-V"`; LV = ln of PV: item I1, `unit_price Decimal("1.00")`.
3. P3 = po `po_number "PO-3"`; L3 = ln of P3: item I1, `unit_price Decimal("6.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L1.id, L3.id}`.

### PII-F-03 — the excluded PO's lines are left out, all others kept
- **Rules:** `_fetch_history_lines` R1, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.
2. P2 = po `po_number "PO-2"`; L2 = ln of P2: item I1, `unit_price Decimal("6.00")`.
3. L2B = ln of P2: item I1, `unit_price Decimal("6.50")`, `line_number 2`.
4. P3 = po `po_number "PO-3"`; L3 = ln of P3: item I1, `unit_price Decimal("7.00")`.
5. L3B = ln of P3: item I1, `unit_price None`, `line_number 2`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=P2.id)`.

**Then**
1. returns: `ids(result) == {L1.id, L3.id, L3B.id}`.

### PII-F-04 — only the asked items are returned
- **Rules:** `_fetch_history_lines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. L1 = ln of P1: item I1, `unit_price Decimal("5.00")`, `line_number 1`.
3. L2 = ln of P1: item I2, `unit_price Decimal("6.00")`, `line_number 2`.
4. L3 = ln of P1: item I3, `unit_price Decimal("7.00")`, `line_number 3`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I2.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L2.id}`.

### PII-F-05 — an unknown item id matches nothing
- **Rules:** `_fetch_history_lines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`; ln of P1: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[MISSING], exclude_po_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PII-F-06 — POs of earlier and later workspaces are never returned
- **Rules:** `_fetch_history_lines` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po `po_number "PO-0"`; L0 = ln of P0: item I0, `unit_price Decimal("1.00")`.
2. P1 = po `po_number "PO-1"`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.
3. P9 = W2 po `po_number "PO-9"`; L9 = ln of P9: item I9, `unit_price Decimal("2.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I0.id, I1.id, I9.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L1.id}`.

### PII-F-07 — other workspaces' POs holding a W1 item are never returned
- **Rules:** `_fetch_history_lines` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 po `po_number "PO-0"`; L0 = ln of P0: item I1, `unit_price Decimal("1.00")`.
2. P1 = po `po_number "PO-1"`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.
3. P9 = W2 po `po_number "PO-9"`; L9 = ln of P9: item I1, `unit_price Decimal("2.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L1.id}`.

### PII-F-08 — any status counts and an unpriced line is returned
- **Rules:** `_fetch_history_lines` R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. SD = `Status(workspace_id=W1.id, name="Draft", comment="")`; SC = `Status(workspace_id=W1.id, name="Complete", comment="")`.
2. P1 = po `po_number "PO-1"`, but `current_status_id SD.id`; L1 = ln of P1: item I1, `unit_price None`.
3. P2 = po `po_number "PO-2"`, but `current_status_id SC.id`; L2 = ln of P2: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L1.id, L2.id}`.
2. returns: `[l.unit_price for l in result if l.line_id == L1.id] == [None]`.

### PII-F-09 — a line with a later workspace's workspace_id is left out
- **Rules:** `_fetch_history_lines` R1a [BUG-2540]
- **Kind:** bug
- **Expect:** xfail BUG-2540
- **Fails today on:** Then 2 (LX is returned)

**Given**
1. P1 = po `po_number "PO-1"`.
2. L1 = ln of P1: item I1, `unit_price Decimal("5.00")`, `line_number 1`.
3. LX = ln of P1: item I1, `unit_price Decimal("1.00")`, `line_number 2`, but `workspace_id W2.id`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `L1.id in ids(result)`.
2. returns: `ids(result) == {L1.id}`.

### PII-F-10 — a line with an earlier workspace's workspace_id is left out
- **Rules:** `_fetch_history_lines` R1a [BUG-2540]
- **Kind:** bug
- **Expect:** xfail BUG-2540
- **Fails today on:** Then 2 (LX is returned)

**Given**
1. P1 = po `po_number "PO-1"`.
2. LX = ln of P1: item I1, `unit_price Decimal("1.00")`, `line_number 1`, but `workspace_id W0.id`.
3. L1 = ln of P1: item I1, `unit_price Decimal("5.00")`, `line_number 2`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `L1.id in ids(result)`.
2. returns: `ids(result) == {L1.id}`.

### PII-F-11 — the W1 line next to a foreign line is still returned
- **Rules:** `_fetch_history_lines` R1, R1a (regression part)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`.
2. LX = ln of P1: item I1, `unit_price Decimal("1.00")`, `line_number 1`, but `workspace_id W2.id`.
3. L1 = ln of P1: item I1, `unit_price Decimal("5.00")`, `line_number 2`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `L1.id in ids(result)`.

### PII-F-12 — no order_date falls back to the UTC day of created_at; a future date is kept
- **Rules:** `_fetch_history_lines` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`, `created_at datetime(2026, 3, 4, 23, 30)` (no `order_date`); L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.
2. P2 = po `po_number "PO-2"`, `order_date date(2030, 1, 1)`; L2 = ln of P2: item I1, `unit_price Decimal("6.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `{(l.line_id, l.order_date) for l in result} == {(L1.id, date(2026, 3, 4)), (L2.id, date(2030, 1, 1))}`.

### PII-F-13 — a later workspace's supplier is treated as no supplier
- **Rules:** `_fetch_history_lines` R4a [BUG-2540]
- **Kind:** bug
- **Expect:** xfail BUG-2540
- **Fails today on:** Then 2 (AC9's id and name are returned)

**Given**
1. P1 = po `po_number "PO-1"`, `account_id AC9.id`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L1.id}`.
2. returns: `result[0].account_id is None`, `result[0].account_name is None`.

### PII-F-14 — an earlier workspace's supplier is treated as no supplier
- **Rules:** `_fetch_history_lines` R4a [BUG-2540]
- **Kind:** bug
- **Expect:** xfail BUG-2540
- **Fails today on:** Then 2 (AC0's id and name are returned)

**Given**
1. P1 = po `po_number "PO-1"`, `account_id AC0.id`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L1.id}`.
2. returns: `result[0].account_id is None`, `result[0].account_name is None`.

### PII-F-15 — a line with a foreign supplier is still returned
- **Rules:** `_fetch_history_lines` R1, R4a (regression part)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`, `account_id AC9.id`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `ids(result) == {L1.id}`.
2. returns: `result[0].unit_price == Decimal("5.00")`.

### PII-F-16 — no supplier gives no name; a deleted or inactive supplier is still named
- **Rules:** `_fetch_history_lines` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AD = `Account(workspace_id=W1.id, name="Gone Co", is_deleted=True, is_active=False)`.
2. P1 = po `po_number "PO-1"`; L1 = ln of P1: item I1, `unit_price Decimal("5.00")`.
3. P2 = po `po_number "PO-2"`, `account_id AD.id`; L2 = ln of P2: item I1, `unit_price Decimal("6.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[I1.id], exclude_po_id=MISSING)`.

**Then**
1. returns: `{(l.line_id, l.account_id, l.account_name) for l in result} == {(L1.id, None, None), (L2.id, AD.id, "Gone Co")}`.

### PII-F-17 — empty item_ids returns an empty list
- **Rules:** `_fetch_history_lines` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `po_number "PO-1"`; ln of P1: item I1, `unit_price Decimal("5.00")`.

**When**
- `result = svc._fetch_history_lines(db, workspace_id=W1.id, item_ids=[], exclude_po_id=MISSING)`.

**Then**
1. returns: `result == []`.

## `_pick_last_ordered`

### PII-L-01 — no lines gives None
- **Rules:** `_pick_last_ordered` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = svc._pick_last_ordered([])`.

**Then**
1. returns: `result is None`.

### PII-L-02 — the latest date wins over a higher line id
- **Rules:** `_pick_last_ordered` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2))`.
2. `b = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("3.00"), order_date=date(2026, 3, 1))`.

**When**
- `result = svc._pick_last_ordered([b, a])`.

**Then**
1. returns: `result.purchase_order_id == 50`, `result.order_date == date(2026, 3, 2)`.

### PII-L-03 — on a date tie the highest line id wins
- **Rules:** `_pick_last_ordered` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2))`.
2. `b = HL(line_id=5, purchase_order_id=90, unit_price=Decimal("3.00"), order_date=date(2026, 3, 2))`.

**When**
- `result = svc._pick_last_ordered([b, a])`.

**Then**
1. returns: `result.purchase_order_id == 10`.

### PII-L-04 — an unpriced, zero-priced, supplier-less or future line can be last
- **Rules:** `_pick_last_ordered` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("0.00"), order_date=date(2030, 1, 1))`.
2. `b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
3. `c = HL(line_id=3, purchase_order_id=30, unit_price=None, order_date=date(2029, 1, 1))`.

**When**
- `result = (svc._pick_last_ordered([b, a]), svc._pick_last_ordered([b, c]))`.

**Then**
1. returns: `result[0].purchase_order_id == 10`, `result[0].unit_price == Decimal("0.00")`.
2. returns: `result[1].purchase_order_id == 30`, `result[1].unit_price is None`.

### PII-L-05 — with no dated line the highest line id wins
- **Rules:** `_pick_last_ordered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("4.00"), order_date=None)`.
2. `b = HL(line_id=5, purchase_order_id=90, unit_price=Decimal("3.00"), order_date=None)`.

**When**
- `result = svc._pick_last_ordered([b, a])`.

**Then**
1. returns: `result.purchase_order_id == 10`.

### PII-L-06 — an undated line is ignored when another line has a date
- **Rules:** `_pick_last_ordered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("4.00"), order_date=None)`.
2. `b = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("3.00"), order_date=date(2026, 3, 1))`.

**When**
- `result = svc._pick_last_ordered([a, b])`.

**Then**
1. returns: `result.purchase_order_id == 50`.

## `_pick_min_price_ref`

### PII-M-01 — None, zero and negative prices never count
- **Rules:** `_pick_min_price_ref` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=None, order_date=date(2026, 3, 1))`.
2. `b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1))`.
3. `c = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("-1.00"), order_date=date(2026, 3, 1))`.
4. `d = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("0.01"), order_date=date(2026, 3, 1))`.

**When**
- `result = svc._pick_min_price_ref([a, b, c, d])`.

**Then**
1. returns: `result.purchase_order_id == 40`, `result.unit_price == Decimal("0.01")`.

### PII-M-02 — no candidate gives None
- **Rules:** `_pick_min_price_ref` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=None, order_date=date(2026, 3, 1))`.
2. `b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1))`.

**When**
- `result = (svc._pick_min_price_ref([a, b]), svc._pick_min_price_ref([]))`.

**Then**
1. returns: `result[0] is None`.
2. returns: `result[1] is None`.

### PII-M-03 — both window bounds are inclusive
- **Rules:** `_pick_min_price_ref` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 2, 28))`.
2. `b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))`.
3. `c = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("6.00"), order_date=date(2026, 3, 31))`.
4. `d = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("1.00"), order_date=date(2026, 4, 1))`.

**When**
- `result = (svc._pick_min_price_ref([a, b, c, d], from_date=date(2026, 3, 1), to_date=date(2026, 3, 31)), svc._pick_min_price_ref([a, c, d], from_date=date(2026, 3, 1), to_date=date(2026, 3, 31)))`.

**Then**
1. returns: `result[0].purchase_order_id == 20`.
2. returns: `result[1].purchase_order_id == 30`.

### PII-M-04 — an undated line is dropped by a window; one bound alone applies no window
- **Rules:** `_pick_min_price_ref` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=None)`.
2. `b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("5.00"), order_date=date(2026, 3, 10))`.
3. `c = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2025, 1, 1))`.

**When**
- `result = (svc._pick_min_price_ref([a, b], from_date=date(2026, 3, 1), to_date=date(2026, 3, 31)), svc._pick_min_price_ref([b, c], from_date=date(2026, 3, 1)), svc._pick_min_price_ref([b, c], to_date=date(2024, 1, 1)))`.

**Then**
1. returns: `result[0].purchase_order_id == 20`.
2. returns: `result[1].purchase_order_id == 30`.
3. returns: `result[2].purchase_order_id == 30`.

### PII-M-05 — the cheapest wins over earlier and lower ids
- **Rules:** `_pick_min_price_ref` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("5.01"), order_date=date(2026, 1, 1))`.
2. `b = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))`.

**When**
- `result = svc._pick_min_price_ref([a, b])`.

**Then**
1. returns: `result.purchase_order_id == 90`, `str(result.unit_price) == "5.00"`.

### PII-M-06 — on a price tie the earliest date wins over a lower PO id
- **Rules:** `_pick_min_price_ref` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 2))`.
2. `b = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))`.
3. `c = HL(line_id=8, purchase_order_id=80, unit_price=Decimal("5.00"), order_date=None)`.

**When**
- `result = (svc._pick_min_price_ref([a, b]), svc._pick_min_price_ref([a, b, c]))`.

**Then**
1. returns: `result[0].purchase_order_id == 90`.
2. returns: `result[1].purchase_order_id == 80`.

### PII-M-07 — on a price and date tie the lowest PO id wins over a lower line id
- **Rules:** `_pick_min_price_ref` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=90, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))`.
2. `b = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1))`.

**When**
- `result = svc._pick_min_price_ref([a, b])`.

**Then**
1. returns: `result.purchase_order_id == 10`.

### PII-M-08 — on a full tie within one PO the lowest line id wins
- **Rules:** `_pick_min_price_ref` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=9, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
2. `b = HL(line_id=4, purchase_order_id=10, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1), account_id=12, account_name="Beta")`.

**When**
- `result = svc._pick_min_price_ref([a, b])`.

**Then**
1. returns: `result.account_id == 12`, `result.account_name == "Beta"`.

## `_pick_avg_supplier_lowest`

### PII-A-01 — no candidate gives None
- **Rules:** `_pick_avg_supplier_lowest` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1))` (no supplier).
2. `b = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.

**When**
- `result = (svc._pick_avg_supplier_lowest([a, b]), svc._pick_avg_supplier_lowest([]))`.

**Then**
1. returns: `result[0] is None`.
2. returns: `result[1] is None`.

### PII-A-02 — supplier-less, unpriced, zero and negative lines never compete
- **Rules:** `_pick_avg_supplier_lowest` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `n = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1))` (no supplier).
2. `z = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("0.00"), order_date=date(2026, 3, 1), account_id=21, account_name="Zero")`.
3. `g = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("-1.00"), order_date=date(2026, 3, 1), account_id=31, account_name="Neg")`.
4. `u = HL(line_id=4, purchase_order_id=40, unit_price=None, order_date=date(2026, 3, 1), account_id=41, account_name="None Co")`.
5. `a = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("5.00"), order_date=date(2026, 3, 1), account_id=51, account_name="Acme")`.

**When**
- `result = svc._pick_avg_supplier_lowest([n, z, g, u, a])`.

**Then**
1. returns: `result.account_id == 51`, `result.purchase_order_id == 50`.

### PII-A-03 — the average is weighted by quantity
- **Rules:** `_pick_avg_supplier_lowest` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme", quantity_ordered=Decimal("10.00"))`.
2. `a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("10.00"), order_date=date(2026, 3, 2), account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))`.
3. `b = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("3.00"), order_date=date(2026, 3, 3), account_id=12, account_name="Beta")`.

**When**
- `result = svc._pick_avg_supplier_lowest([b, a1, a2])`.

**Then**
1. returns: `result.account_id == 11`, `result.purchase_order_id == 10`.

### PII-A-04 — averages are exact, not rounded
- **Rules:** `_pick_avg_supplier_lowest` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("3.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))`.
2. `a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("3.50"), order_date=date(2026, 3, 2), account_id=11, account_name="Acme", quantity_ordered=Decimal("2.00"))`.
3. `b = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("3.33"), order_date=date(2026, 3, 3), account_id=12, account_name="Beta")`.

**When**
- `result = svc._pick_avg_supplier_lowest([a1, a2, b])`.

**Then**
1. returns: `result.account_id == 12`, `result.purchase_order_id == 30`.

### PII-A-05 — a quantity of 0 or below weighs 1
- **Rules:** `_pick_avg_supplier_lowest` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme", quantity_ordered=Decimal("0.00"))`.
2. `a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("10.00"), order_date=date(2026, 3, 2), account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))`.
3. `c1 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("10.20"), order_date=date(2026, 3, 1), account_id=13, account_name="Cobalt", quantity_ordered=Decimal("-5.00"))`.
4. `c2 = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("1.00"), order_date=date(2026, 3, 2), account_id=13, account_name="Cobalt", quantity_ordered=Decimal("1.00"))`.
5. `b = HL(line_id=5, purchase_order_id=50, unit_price=Decimal("6.00"), order_date=date(2026, 3, 3), account_id=12, account_name="Beta")`.

**When**
- `result = (svc._pick_avg_supplier_lowest([b, a1, a2]), svc._pick_avg_supplier_lowest([b, c1, c2]))`.

**Then**
1. returns: `result[0].account_id == 11`, `result[0].purchase_order_id == 10`.
2. returns: `result[1].account_id == 13`, `result[1].purchase_order_id == 40`.

### PII-A-06 — on an equal average, more distinct orders win
- **Rules:** `_pick_avg_supplier_lowest` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `b = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
2. `a1 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2), account_id=12, account_name="Beta")`.
3. `a2 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3), account_id=12, account_name="Beta")`.

**When**
- `result = svc._pick_avg_supplier_lowest([b, a1, a2])`.

**Then**
1. returns: `result.account_id == 12`.

### PII-A-07 — orders are counted distinct, not lines
- **Rules:** `_pick_avg_supplier_lowest` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
2. `a2 = HL(line_id=2, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
3. `a3 = HL(line_id=3, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
4. `b1 = HL(line_id=4, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2), account_id=12, account_name="Beta")`.
5. `b2 = HL(line_id=5, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3), account_id=12, account_name="Beta")`.

**When**
- `result = svc._pick_avg_supplier_lowest([a1, a2, a3, b1, b2])`.

**Then**
1. returns: `result.account_id == 12`.

### PII-A-08 — the reference is the winner's cheapest line, never its zero line
- **Rules:** `_pick_avg_supplier_lowest` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a0 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("0.00"), order_date=date(2026, 3, 5), account_id=11, account_name="Acme")`.
2. `a1 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("6.00"), order_date=date(2026, 3, 6), account_id=11, account_name="Acme")`.
3. `a2 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("4.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
4. `b = HL(line_id=4, purchase_order_id=40, unit_price=Decimal("9.00"), order_date=date(2026, 3, 1), account_id=12, account_name="Beta")`.

**When**
- `result = svc._pick_avg_supplier_lowest([a0, a1, a2, b])`.

**Then**
1. returns: `result.purchase_order_id == 30`, `result.unit_price == Decimal("4.00")`, `result.account_name == "Acme"`.

### PII-A-09 — reference ties: latest date, then lowest PO id, then lowest line id
- **Rules:** `_pick_avg_supplier_lowest` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `e = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("4.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
2. `l = HL(line_id=9, purchase_order_id=90, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2), account_id=11, account_name="Acme")`.
3. `p = HL(line_id=8, purchase_order_id=20, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2), account_id=11, account_name="Acme")`.
4. `q = HL(line_id=3, purchase_order_id=20, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2), account_id=11, account_name="ACME")`.
5. `n = HL(line_id=7, purchase_order_id=70, unit_price=Decimal("4.00"), order_date=None, account_id=11, account_name="Acme")`.

**When**
- `result = (svc._pick_avg_supplier_lowest([e, l]), svc._pick_avg_supplier_lowest([l, p]), svc._pick_avg_supplier_lowest([p, q]), svc._pick_avg_supplier_lowest([n, e]))`.

**Then**
1. returns: `result[0].purchase_order_id == 90`.
2. returns: `result[1].purchase_order_id == 20`.
3. returns: `result[2].purchase_order_id == 20`, `result[2].account_name == "ACME"`.
4. returns: `result[3].purchase_order_id == 10`.

### PII-A-10 — a full tie goes to the name first case-insensitively, not the first line
- **Rules:** `_pick_avg_supplier_lowest` R5 [BUG-2543]
- **Kind:** bug
- **Expect:** xfail BUG-2543
- **Fails today on:** Then 2 (the first-seen supplier "Beta" wins)

**Given**
1. `b = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Beta")`.
2. `a = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2), account_id=22, account_name="alpha")`.

**When**
- `result = svc._pick_avg_supplier_lowest([b, a])`.

**Then**
1. returns: `result.unit_price == Decimal("2.00")`.
2. returns: `result.account_id == 22`, `result.account_name == "alpha"`.

### PII-A-11 — on equal names the lower account id wins, not the first line
- **Rules:** `_pick_avg_supplier_lowest` R5 [BUG-2543]
- **Kind:** bug
- **Expect:** xfail BUG-2543
- **Fails today on:** Then 2 (the first-seen supplier 22 wins)

**Given**
1. `b = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=22, account_name="same")`.
2. `a = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2), account_id=11, account_name="SAME")`.

**When**
- `result = svc._pick_avg_supplier_lowest([b, a])`.

**Then**
1. returns: `result.unit_price == Decimal("2.00")`.
2. returns: `result.account_id == 11`, `result.purchase_order_id == 20`.

### PII-A-12 — a cheaper supplier listed first is not replaced by a pricier one with more orders
- **Rules:** `_pick_avg_supplier_lowest` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.
2. `b1 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2), account_id=12, account_name="Beta")`.
3. `b2 = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3), account_id=12, account_name="Beta")`.

**When**
- `result = svc._pick_avg_supplier_lowest([a, b1, b2])`.

**Then**
1. returns: `result.account_id == 11`, `result.purchase_order_id == 10`.

### PII-A-13 — on an equal average, a later supplier with fewer orders does not replace the first
- **Rules:** `_pick_avg_supplier_lowest` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `b1 = HL(line_id=1, purchase_order_id=20, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=12, account_name="Beta")`.
2. `b2 = HL(line_id=2, purchase_order_id=30, unit_price=Decimal("2.00"), order_date=date(2026, 3, 2), account_id=12, account_name="Beta")`.
3. `a = HL(line_id=3, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 3), account_id=11, account_name="Acme")`.

**When**
- `result = svc._pick_avg_supplier_lowest([b1, b2, a])`.

**Then**
1. returns: `result.account_id == 12`.

### PII-A-14 — a quantity between 0 and 1 weighs its quantity, not 1
- **Rules:** `_pick_avg_supplier_lowest` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a1 = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("1.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme", quantity_ordered=Decimal("0.50"))`.
2. `a2 = HL(line_id=2, purchase_order_id=20, unit_price=Decimal("4.00"), order_date=date(2026, 3, 2), account_id=11, account_name="Acme", quantity_ordered=Decimal("1.00"))`.
3. `b = HL(line_id=3, purchase_order_id=30, unit_price=Decimal("2.75"), order_date=date(2026, 3, 3), account_id=12, account_name="Beta", quantity_ordered=Decimal("1.00"))`.

**When**
- `result = svc._pick_avg_supplier_lowest([a1, a2, b])`.

**Then**
1. returns: `result.account_id == 12`, `result.purchase_order_id == 30`.

## `_HistoryLine`

### PII-DC-01 — a history line is frozen
- **Rules:** `_HistoryLine` (spec Not specified: frozen dataclass; Gap log G1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `h = HL(line_id=1, purchase_order_id=10, unit_price=Decimal("2.00"), order_date=date(2026, 3, 1), account_id=11, account_name="Acme")`.

**When**
- `h.unit_price = Decimal("1.00")` under `raises: FrozenInstanceError`.

**Then**
1. raises: `FrozenInstanceError`.
2. returns: `h.unit_price == Decimal("2.00")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `_pick_avg_supplier_lowest` R7 | dead-code list (spec FU-1) | unreachable: weights are always > 0 (spec R7; a weight may be below 1, e.g. 0.50 in A-14), so no input reaches it; removal is the reviewer's call |

## Spec gaps
None. Gaps 1–2 of revision 1 were closed in spec round 2 (Gap log G1, G2).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_dec` | R1 | PII-D-01 |
| `_dec` | R2 | PII-D-02, PII-D-03 |
| `_dec` | Errors | PII-D-04 |
| `_to_ref` | R1 | PII-R-01, PII-R-02 |
| `get_item_price_insights` | R1 | PII-G-01, PII-G-02, PII-G-03, PII-G-04 |
| `get_item_price_insights` | Errors row 1 (404) | PII-G-01, PII-G-02, PII-G-03 |
| `get_item_price_insights` | R2 | PII-G-05 |
| `get_item_price_insights` | R3 | PII-G-06, PII-G-07, PII-G-10, PII-G-11 |
| `get_item_price_insights` | R3a [BUG-2541] | PII-G-12, PII-G-13, PII-G-14 (regression PII-G-11) |
| `get_item_price_insights` | R4 | PII-G-08, PII-G-09, PII-G-15, PII-G-16 |
| `get_item_price_insights` | R5 | PII-G-08, PII-G-17 |
| `get_item_price_insights` | R6 | PII-G-08, PII-G-18, PII-G-19, PII-G-20 |
| `get_item_price_insights` | R6 [BUG-2542] | PII-G-22 |
| `get_item_price_insights` | R7 | PII-G-21, PII-G-01 |
| `_fetch_history_lines` | R1 | PII-F-01 … PII-F-07, PII-G-17 |
| `_fetch_history_lines` | R1a [BUG-2540] | PII-F-09, PII-F-10 (regression PII-F-11) |
| `_fetch_history_lines` | R2 | PII-F-08 |
| `_fetch_history_lines` | R3 | PII-F-12 |
| `_fetch_history_lines` | R4 | PII-F-01, PII-F-16 |
| `_fetch_history_lines` | R4a [BUG-2540] | PII-F-13, PII-F-14, PII-G-15, PII-G-16 (regression PII-F-15) |
| `_fetch_history_lines` | R5 | PII-F-01, PII-F-08 |
| `_fetch_history_lines` | R6 | PII-F-03 (set checks throughout) |
| `_fetch_history_lines` | R7 | PII-F-17 |
| `_pick_last_ordered` | R1 | PII-L-01 |
| `_pick_last_ordered` | R2 | PII-L-02, PII-L-03, PII-L-04, PII-G-08 |
| `_pick_last_ordered` | R3 | PII-L-05, PII-L-06 |
| `_pick_min_price_ref` | R1 | PII-M-01 |
| `_pick_min_price_ref` | R2 | PII-M-03, PII-M-04 |
| `_pick_min_price_ref` | R3 | PII-M-02 |
| `_pick_min_price_ref` | R4 | PII-M-05, PII-M-06, PII-M-07, PII-M-08 |
| `_pick_min_price_ref` | R5 | PII-G-19 |
| `_pick_avg_supplier_lowest` | R1 | PII-A-01, PII-A-02 |
| `_pick_avg_supplier_lowest` | R2 | PII-A-01 |
| `_pick_avg_supplier_lowest` | R3 | PII-A-03, PII-A-04, PII-A-05, PII-A-14 |
| `_pick_avg_supplier_lowest` | R4 | PII-A-03, PII-A-04, PII-A-06, PII-A-07, PII-A-12, PII-A-13, PII-A-14 |
| `_pick_avg_supplier_lowest` | R5 [BUG-2543] | PII-A-10, PII-A-11 |
| `_pick_avg_supplier_lowest` | R6 | PII-A-08, PII-A-09 |
| `_pick_avg_supplier_lowest` | R7 | Deferred (unreachable) |
| `_HistoryLine` | frozen (Not specified, G1) | PII-DC-01 |
