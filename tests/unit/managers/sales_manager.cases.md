# Test cases — `app/managers/sales_manager.py`

> **Spec:** `tests/unit/managers/sales_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 347 cases · 263 expected-to-pass · 84 expected-to-fail (bugs) · 16 deferred
> **Revision:** 10 (2026-11-19) — re-run after verification (`sales_manager.verify.md` on cases revision 9, findings F13 and F14, both `case-missing`); no spec change. Changes:
> - F13 (surviving mutants `moc_r5_anyws`, `hor_anyws`): new SM-MOC-17. SO1 (W1) has pending returns only in W0 (built before W1) and W2 (built after W1), so both a `<=` and a `>=` workspace filter would be caught. The call still completes (no R5 400) and HOR(SO1) is `False`. Expect is **pass**: spec R5 and RP2 count only "this order's returns in this workspace" (return manager `has_open_return` R1, marked ✅), with no bug tag, so today's code already scopes by workspace and the mutants show only that the cards were missing.
> - F14 (surviving mutant `moc_commit`): new SM-MOC-18, a commit spy on `mark_order_complete` with the default setup (0 calls), `Author: claude`, pass.
> - Counts: 345 + 2 new = 347 (263 pass, 84 xfail, 16 deferred). No open gaps.
>
> **Revision 9 (earlier, 2026-11-19):** the owner refined OQ-48 (spec revision 2026-11-17, second note): `reopen_for_return` R2 / new R2a, plus the new shared section *Return-in-progress state* RP1–RP7. While a return is open, a completed order stays completed in storage and shows "return in progress" through the derived `has_open_return`. The invoice stays frozen, and `reopen_for_return` writes none of this. Changes:
> - Conventions: new HOR(order), a read of the return manager's flag used only in Then lines.
> - SM-ROR-02 (still strict xfail BUG-2790): the Given now has a pending return. The Then also checks HOR is `True` and the order is still completed. That HOR check holds today, so it comes before the failing return check; the failing line is now Then 3. Cites R2, R2a, RP1.
> - SM-ROR-06 / 07: still strict xfail, same Then; now cite R2, R2a, RP1.
> - Citations only: SM-ROR-03 now cites R2 and RP4, and gains one line, HOR `True` after the call, as the pass side of ROR-02. SM-ROR-08 / 09 now cite R2a; SM-ROR-10 cites R2a and "flush only".
> - New RP6 / RP7 cards, wherever this manager is reached:
>   - `reopen_for_return`: SM-ROR-11 (two returns open at once; strict xfail), SM-ROR-12 (its pass side), SM-ROR-13 (one return completed, one open; strict xfail), SM-ROR-14 (the last return cancelled, no return pending; strict xfail).
>   - `mark_order_complete` R2 short-circuit on a completed order, all pass: SM-MOC-14 (one completed, one open: no 400, HOR `True`, nothing written), SM-MOC-15 (the last return completed: HOR `False`, nothing written), SM-MOC-16 (the last return cancelled / voided: HOR `False`, nothing written).
> - Deferred: two new rows. RP2 / RP3 (the response field) go to `SalesService` / `SalesOrderResponse`. The RP6 (b)/(c) and RP7 transitions go to `SalesOrderReturnManager` and `void_invoice` R3c. No response-field cards here.
> - Coverage matrix: new R2a row, a *Return-in-progress state* block RP1–RP7, and an MOC R2 × RP6 row.
> - Counts: 338 + 7 new = 345. Pass 257 + 4 = 261. Xfail 81 + 3 = 84. Deferred 14 + 2 = 16. No open gaps.
>
> **Revision 8 (earlier, 2026-11-17):** spec revision 2026-11-17 (owner, OQ-48): `reopen_for_return` R2 now says a return never reopens a completed order, and its invoice stays frozen [BUG-2790]. Changes:
> - SM-ROR-02 (ID kept, same subject: a completed order) is now strict `xfail BUG-2790`. It expects the intended result: returns `False`, the order stays completed with the same `completed_at` / `completed_by`, no event, NW. It fails today on the return value. Its Given now pins `completed_at` and links a confirmed invoice.
> - New pass cards for what holds both today and after the fix (the return value is checked only as a `bool`, since it changes with the fix): SM-ROR-03 (invoice row, invoice link, other order flags, the return row and stock are untouched), SM-ROR-08 / 09 (another workspace's completed order: its invoice and W1's own completed order are untouched), SM-ROR-10 (commit spy).
> - New cards for another workspace's order, a workspace built before W1 (W0) and one after it (W2): SM-ROR-04 / 05 (not completed → `False`, nothing written; pass), SM-ROR-06 / 07 (completed → stays completed; strict xfail BUG-2790).
> - Conventions: new W0, SO0, A0/F0. Deferred: new row for `SalesService.start_return` / `account_invoice_manager` F2, because the spec allows the fix to drop the call there instead.
> - Counts: 330 + 8 new = 338. Pass 252 − 1 (ROR-02) + 6 = 257. Xfail 78 + 1 + 2 = 81. Deferred 13 + 1 = 14. No open gaps.
>
> **Revision 7 (earlier):** re-run after verification (`sales_manager.verify.md`, cases revision 6); no spec change since revision 6. Changes:
> - Verify F5 / surviving mutant #4 (`case-missing`, still OPEN after revision 6): new SM-UD-22. SM-UD-21 could not tell "unset fields are not counted" from "unset fields are counted", because its sent field (`notes`) changed anyway and the unset field has no label. In UD-22 nothing that is sent differs from the stored row, so the unset field alone decides the outcome: no event, row unchanged, `updated_by` unchanged (R5). If unset fields were counted, an event `"Delivery DEL-2026-004 updated ()"` would be logged. Of the two designs the report offers, the "nothing sent differs" one was chosen over the labelled-field one (best-practice default, delegated by reviewer): it tests the R5 no-op boundary directly and does not depend on label wording.
> - SM-UD-21 is kept unchanged (ID stable). It still pins that an unset field is not written when another field changes.
> - Counts: 329 + 1 new = 330 (252 pass, 78 xfail). No open gaps.
>
> **Revision 6 (earlier):** re-run after verification (`sales_manager.verify.md`, cases revision 5) on the spec with new Gap log G17–G18. Changes:
> - Verify F2/F3 + spec G17 (`quantity_refunded` is NOT NULL, so a stored line can never hold `None`): retired SM-CD-42, SM-FSI-10, SM-RFD-07 as unreachable (same treatment as LA-06/AA-12/RMA-09). The "`None` refunded = 0" clause stays covered by the pure-helper cases DLV-07 and FUL-05.
> - Verify F4 + spec G18 (`'locked'` invoice status is a dead value): no case designed, per spec R3 and Notes. The LCK coverage row notes this. Surviving mutant #6 (L536) is accepted as dead per the spec.
> - Verify F5 / surviving mutant #4 (`case-missing`): new SM-UD-21. The ad-hoc data model has an unset field (`delivery_status`) whose non-`None` default differs from the stored value. The case expects it to be neither written nor logged: only *sent* fields count (R3 "omitted → left unchanged", R4 "sent value"). R6's "any field of `data`" is read as "any sent field" (best-practice default, delegated by reviewer: PATCH semantics).
> - Executor findings F1, F6–F12 need no case change: the case text already states those assertions.
> - Counts: 331 − 3 retired + 1 new = 329 (251 pass, 78 xfail). No open gaps.
>
> **Revision 5 (earlier):** re-run on the spec with Gap log G1–G16 (no spec change since revision 4; no verify report). Full self-check over the whole file found one setup defect: several setups left extra orders/deliveries on the default number, which collides under today's global unique index. Changes:
> - Conventions: SO2 / SOX now have fixed numbers. Unnumbered extra deliveries get `DEL-2026-001..` in listed order.
> - CD-17 names its three delivery numbers and also asserts the new delivery line.
> - No case added or removed; Counts unchanged. No open gaps.
>
> **Revision 4 (earlier):** spec Gap log closed G16 with new `create_sales_order_with_items` R2a (fallback unreachable after BUG-728; test it in `order_catalog_items`). Changes:
> - No case added or removed: revision 3 already applied that default (CO-11 retired, CO-50, Deferred row).
> - Coverage matrix: new R2a row (CO-50 + Deferred); stale rows fixed. Retired CO-11, LA-06, AA-12, RMA-09 removed. Missing CO-46..53 and CD-44..46 added, plus a new `create_delivery_with_items` R10a row.
> - G16 removed from Spec gaps. No open gaps.
>
> **Revision 3 (earlier):** spec Gap log closed G1–G15. Changes:
> - G1: real table names used in Conventions. ID is now an item with `is_active = False` (items have no soft-delete column). New CO-46 covers a `client` tag that is inactive.
> - G2: BUG-727 race-freedom is integration-only per the spec Overview. The Deferred row now cites that.
> - G3/R10a: CD-14 accepts either write order. New CD-46: a wrong-order line after a valid line still leaves no delivery row.
> - G4: CD-20/21 now pin the repeated-line message.
> - G5: CO-30..37 now pin the 404 details. New ordering cases: CO-49 (R1 before R12), CO-50 (R12 before R2), CO-52/53 (account → client → factory). CO-11 retired.
> - G6: CD-15/18 and CPD-22/23/25 now assert exact messages. Setup is expired before the action.
> - G7/R13: the manager validates every line before it writes. New CO-47/48 and CD-44/45.
> - G8: AA-12, RMA-09 and LA-06 retired as unreachable.
> - G9: CD-26 now expects the exact `ValueError`.
> - G10: CO-22 asserts NW. New CO-51 covers a missing `factory_id` key.
> - G11: CD-19 now requires the lock on `sales_order_items` only.
> - G13: CD-38 expects the field to be gone from `SalesDeliveryCreate`.
> - G14: UD-11 now asserts the `"updated ()"` event.
> - G15: no case change.
> - New gap G16.
>
> **Revision 2 (earlier):** spec unchanged (no verify report yet); self-check pass over the whole file: Counts and per-callable tallies recounted (were stale), return-value convention added so every success case asserts the return, SEC-08 now asserts NW, UD-19 kind corrected to `boundary` (it is a pass case), G15 added (spec Notes cite the wrong BUG-720 rule number for `mark_order_complete`).

## Reviewer summary
- **Per callable:** `all_deliverable_items_delivered` 9 · `all_fulfilment_items_fulfilled` 6 · `create_sales_order_with_items` 52 (22 bug) · `create_delivery_with_items` 45 (18 bug) · `complete_delivery` 28 (9 bug) · `cancel_delivery` 9 (2 bug) · `update_delivery` 22 (6 bug) · `fulfill_service_item` 19 (5 bug) · `_recompute_is_fully_delivered` 7 (1 bug) · `_base_sections_confirmed` 4 · `is_so_financially_locked` 5 · `unlink_invoice_from_so` 3 · `set_section_confirm` 22 (1 bug) · `reset_approvals` 6 · `apply_post_invoice_confirms` 4 · `mark_order_complete` 18 (1 bug) · `reopen_for_return` 14 (6 bug) · `_invoice_payment_status` 3 · `sync_so_for_linked_invoice` 4 · `sync_so_paid` 7 · `list_approvers` 5 · `approval_summary` 11 (3 bug) · `add_approver` 12 (4 bug) · `remove_approver` 8 (3 bug) · `set_approval` 14 (3 bug) · `log_event` 6 · `list_events` 4.
- **Notable design choices:**
  - The BUG-720 (HR-10) locks are checked by capturing SQL and looking for `SELECT … FOR UPDATE` on the named table before the first write. This follows `to_inventory` / `inventory_movements`. The two-session race itself is Deferred to integration tests.
  - BUG-727 (race-free numbering) has no unit case. The spec marks it integration-only, so it is Deferred.
  - BUG-723/724/725/730 xfail cases assert "nothing written", per R10a. The R10 pass cases (CD-10, 11, 14, 43) assert only what holds whichever order the fix uses.
  - Schema-range bugs (BUG-362, BUG-021) are tested two ways: by building the API schema directly, and by calling the manager with a bad line (CO-47/48, CD-44/45). The 422 responses are Deferred to the endpoints.
  - The BUG-728 fix runs before the duplicate-item check (R2). Spec R2a says this makes R2's `Item #<id>` name fallback unreachable through this manager, so CO-11 is retired and the fallback is Deferred to `order_catalog_items`.
  - Numbers use Y = the current local year, read in the test. Time is not mocked; UTC stamps are checked against a before/after range.
  - Setup quantities are written with 2 decimals, and the session is expired before the action, so message text is deterministic.
  - A `None` refunded quantity is tested only on the pure helpers (DLV-07, FUL-05). A stored line cannot hold `None` (spec G17), so CD-42, FSI-10 and RFD-07 are retired.
  - UD-21 uses an ad-hoc model whose unset field has a non-`None` default. It pins that only *sent* fields are written and logged (best-practice default, delegated by reviewer).
  - UD-22 uses the same ad-hoc model, but its only sent field equals the stored value. The unset field alone then decides the outcome, and the case expects a full no-op: no event, no write, no `updated_by` stamp (verify F5; best-practice default, delegated by reviewer).
  - `reopen_for_return` (BUG-2790, OQ-48): the cards that expected a reopen are now strict xfail on the intended "stays completed, invoice stays frozen". The pass cards that go with them (ROR-03, 08, 09, 10) check the return only as a `bool`, because its value changes with the fix (`True` today, `False` after). The spec has no workspace rule for this method, so a W0/W2 order passed with `workspace_id=W1` is held to R1/R2 like any other order: `False`, nothing written. The spec allows the fix to drop the call from `SalesService.start_return` instead. If the fix deletes the method, the ROR cards must be retired, and the Deferred row for `start_return` carries the behaviour.
  - Return in progress (OQ-48 refined, RP1–RP7): the state is derived, never stored. Cards here therefore check stored completion unchanged plus the flag's value, read with HOR after the call. The response field (RP2/RP3) and the return transitions themselves (completing or voiding a return) belong to other specs and are Deferred. The "last return closed, nothing written" cases reach this manager only through `mark_order_complete` R2 (MOC-14..16) and `reopen_for_return` (ROR-14).
- **Needs a decision:** None. No open spec gaps.

## Conventions for this module
- **IDs:** `SM` = sales_manager. `DLV` = `all_deliverable_items_delivered`, `FUL` = `all_fulfilment_items_fulfilled`, `CO` = `create_sales_order_with_items`, `CD` = `create_delivery_with_items`, `CPD` = `complete_delivery`, `CAN` = `cancel_delivery`, `UD` = `update_delivery`, `FSI` = `fulfill_service_item`, `RFD` = `_recompute_is_fully_delivered`, `BSC` = `_base_sections_confirmed`, `LCK` = `is_so_financially_locked`, `UNL` = `unlink_invoice_from_so`, `SEC` = `set_section_confirm`, `RA` = `reset_approvals`, `APC` = `apply_post_invoice_confirms`, `MOC` = `mark_order_complete`, `ROR` = `reopen_for_return`, `IPS` = `_invoice_payment_status`, `SLI` = `sync_so_for_linked_invoice`, `SP` = `sync_so_paid`, `LA` = `list_approvers`, `AS` = `approval_summary`, `AA` = `add_approver`, `RMA` = `remove_approver`, `SA` = `set_approval`, `LE` = `log_event`, `LEV` = `list_events`.
- **Workspaces and people:**
  - W1 and W2 are two workspaces. W0 is a third workspace, used only where a case names it. It is built **before** W1, so `W0.id < W1.id < W2.id`.
  - U1 is profile "Alice Rahman", an active member of W1 with position "Sales Lead".
  - U2 is profile "Bob Karim", an active member of W1 with no position.
  - U3 is profile "Chitra Das", a W1 member with status `suspended` and position "Clerk".
  - U4 is profile "Dev Paul", a W1 member with status `invited`.
  - U5 is profile "Esha Roy". She is an active member of **W2 only**, with position "Boss" in W2, and is not a member of W1.
  - Profile display name = the profile's name field.
- **Reference rows:**
  - ST is a `statuses` row with id 10. Create it if it is missing.
  - "Tagged `client`" means an `account_tag_assignments` row (same workspace) to an `account_tags` row of the same workspace with `tag_code = 'client'` and `is_active = True`. TGC1 is that tag in W1, TGS1 a `supplier` tag in W1, and TGX a `client` tag in W2.
  - A1 = account "Acme Traders" in W1, tagged `client`. A2 = account "Steel Supplier Ltd" in W1, tagged `supplier` only. A3 = account "Old Client Co" in W1, assigned only to TGI = a W1 tag with `tag_code 'client'` and `is_active = False`. AX = an account in W2 tagged `client` (TGX). AD = an account in W1 tagged `client` with `is_deleted = True`.
  - F1 = factory "Main Plant" in W1. F2 = a second live factory in W1. FX = a factory in W2. FD = a factory in W1 with `is_deleted = True`.
  - Catalog items in W1: I1 = "Bolt M10" (unit "pcs"), I2 = "Paint 5L" (unit "can"), IS = "Installation" (unit "hour"), IU = "Calibration" (unit `""`). IX = an item in W2. ID = an item in W1 with `is_active = False` (items have no soft-delete column; "live" means `is_active = True`, per spec Notes). IE = an item in W1 whose name is `""`, inserted directly.
  - P1 = a `products` row: W1, F1, I1, `is_available_for_sale = True`, live, `qty = 20`, average cost `4.00`, `min_order_qty` null unless a case says otherwise.
  - DM1 = delivery method "Courier" in W1. DM2 = "Van" in W1. DMX = a method in W2. DMD = a method in W1 with `is_deleted = True`.
- **Builders.** Rows are inserted directly and flushed so they have ids. Every column not named takes its default.
  - `SO(...)` builds an order. Defaults: W1, A1, F1, ST, `order_date = 2026-09-01`, `sales_order_number = "SO-2026-010"`, `contact_name = "Rahim"`, `created_by = U1`, every flag `False`, `invoice_id` null, `total_amount = 0`. SO1 is the default order.
  - `L(...)` builds an order line on an order. Fields: catalog item or free text (`description`), `requires_delivery`, then ordered / delivered / refunded, always written as 2-decimal `Decimal`s. `quantity_returned = 0.00`, `unit_price = 1.00`, `line_total = ordered`.
  - Standard lines on SO1:
    - LA: catalog I1, needs delivery, ordered `10.00`, delivered `0.00`, refunded `0.00`.
    - LB: free text "Custom crate", needs delivery, ordered `5.00`.
    - LB2: free text "Pallet wrap", needs delivery, ordered `3.00`.
    - LS: catalog IS, no delivery, ordered `5.00`.
    - LT: free text "Site survey", no delivery, ordered `2.00`.
    - LU: catalog IU, no delivery, ordered `3.00`.
    - A case lists which of these exist.
  - SO2 = a second order of W1 built with `SO(sales_order_number="SO-2026-012")`; SOX = an order of W2 built with `SO(..., sales_order_number="SO-2026-900")` and that workspace's own account/factory. SO0 = an order of W0 built with `SO(..., sales_order_number="SO-2026-899")`, account A0 (an account of W0 tagged with a `client` tag of W0) and factory F0 (a factory of W0). Every extra order in a setup has a number distinct from SO1's (numbers are globally unique today, BUG-726).
  - When a case's Given lists several deliveries without numbers, they get `DEL-2026-001`, `DEL-2026-002`, … in the order listed (instead of the default), so they neither collide with each other nor with the number the action generates.
  - `D(...)` builds a delivery. Defaults: W1, `delivery_number = "DEL-2026-004"`, status `planned`, DM1, `scheduled_date = 2026-10-05`, `tracking_number = "TRK-100"`, `notes = "Gate 3"`, `created_by = U1`, `updated_by` null, `completion_code` null. `DL(line, qty)` is a delivery line with `item_id` copied from the order line. D1 is a delivery of SO1.
  - `INV(status, payment_status, ws=W1)` is an invoice row linked by setting `order.invoice_id`. "Locked" means an order linked to `INV('confirmed', 'unpaid')`.
  - `RET(order, status)` is a return row of that order.
  - **HOR(order)** = `SalesOrderReturnManager.has_open_return(session, sales_order_id=order.id, workspace_id=order.workspace_id)`. It is a read used only in Then lines, never the action, and is called after the action and the flush. It is `True` while at least one return of the order is `pending` (spec RP2).
  - `AP(order, user, approved, approved_at, assigned_at)` is an approver row. It is W1 unless a case says otherwise.
- **Y** = `datetime.now().year`, read at the start of the test. Orders or deliveries "of year Y" have numbers `SO-Y-nnn` / `DEL-Y-nnn`. Bulk inserts of many orders must satisfy the global unique index today.
- **Time:** nothing is mocked.
  - T0 and T1 are naive `datetime.utcnow()` readings taken just before and just after the action. A UTC stamp "in range" means T0 ≤ value ≤ T1.
  - "Today" means `date.today()`, read in the test.
- **NW (nothing written):** snapshot before the call and compare after, across all workspaces:
  - row counts of `sales_orders`, `sales_order_items`, `sales_order_approvers`, `sales_order_events`, `sales_deliveries`, `sales_delivery_items`, `products` and `product_ledger`;
  - every field of the rows named in the case.
  - Error cases are checked in the same session, right after catching the exception.
- **Table map:** invoices are `account_invoices` (`invoice_status`, `payment_status`; `invoice_type 'receivable'`). Returns are `sales_order_returns` (`status`, plus a unique `return_number` and `created_by`). The ledger is `product_ledger`. A product's "average cost" is `products.avg_cost`. Membership is `workspace_members` (`status`, `position`, `role`). Completion codes are `sales_deliveries.completion_code` and `sales_order_items.fulfillment_completion_code`. All of these follow the spec Notes.
- **Expire before acting:** after setup is flushed, the test calls `session.expire_all()` before the action. Quantities in messages then render from DB values (`4.00`). Values the request passes in render as passed (`5`). The zero floor and "no planned lines" render as `0`. Stock-error numbers are integers.
- **Re-read:** every "Then" on database state is read with a fresh query after `session.flush()`, with the objects expired first. Never trust the in-memory object alone.
- **Return value (every case where the call returns normally, even when the row's Then does not repeat it):**
  - `create_sales_order_with_items` → a `SalesOrder` whose id equals the re-read new order;
  - `create_delivery_with_items` → a 2-tuple `(delivery, order)`: `delivery.id` equals the re-read new delivery, `order.id` equals the order passed in `sales_order_id`;
  - `complete_delivery`, `fulfill_service_item`, `set_section_confirm`, `mark_order_complete` → the order object, `.id` equal to the target order;
  - `cancel_delivery`, `update_delivery` → the delivery, `.id` equal to the target delivery;
  - `add_approver` / `set_approval` → the approver row for (order, user), `.id` equal to the re-read row; `log_event` → the new event, `.id` equal to the re-read row;
  - `unlink_invoice_from_so`, `reset_approvals`, `apply_post_invoice_confirms`, `remove_approver`, `sync_so_for_linked_invoice` → `None`;
  - `_recompute_is_fully_delivered`, `sync_so_paid`, `reopen_for_return`, the pure helpers and the read methods → the value stated in the row.
- **HTTPException checks:** `exc.status_code` and the exact `exc.detail`. **ValueError checks:** `str(exc)` equals the message exactly, unless a case says "contains".
- **DB errors** (`IntegrityError` / `DataError`): the executor wraps the call in `session.begin_nested()` so the session stays usable. The raised type is checked as `sqlalchemy.exc.IntegrityError` / `sqlalchemy.exc.DBAPIError` respectively.
- **Event metadata** is read from the `metadata` JSON column of `sales_order_events` (raw SQL or the model's mapped attribute).
- **SQL capture** (BUG-720 cases only):
  - A SQLAlchemy `before_cursor_execute` listener on the test connection records every statement run during the action only, not the setup.
  - "Locks T before W" means at least one captured statement is a SELECT from table T that contains `FOR UPDATE`, and it comes before the first captured write W.
- **Schema cases** (target `schema`) need no database. "Otherwise valid" is spelled out in each case. Any other field the schema requires is set to a valid value.
- **Externals mocked:** none.
- **Race simulations:** none.

## `all_deliverable_items_delivered`
Lines are transient `SalesOrderItem` objects (not added to the session) with the fields given.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-DLV-01 | R4 | boundary | — | `[]` | returns `True` | pass |
| SM-DLV-02 | R1, R4 | boundary | two lines, `requires_delivery=False`, ordered 10, delivered 0, refunded 0 | call | returns `True` (short non-delivery lines ignored) | pass |
| SM-DLV-03 | R2 | happy | one delivery line ordered 10, delivered 10, refunded 0 | call | returns `True` | pass |
| SM-DLV-04 | R2 | boundary | delivery line ordered 10, delivered 12, refunded 0 | call | returns `True` | pass |
| SM-DLV-05 | R3 | boundary | delivery line ordered 10, delivered 7, refunded 2 | call | returns `False` | pass |
| SM-DLV-06 | R2 | boundary | delivery line ordered 10, delivered 8, refunded 2 | call | returns `True` | pass |
| SM-DLV-07 | R2 | boundary | (a) delivery line ordered 10, delivered 10, refunded `None`; (b) ordered 10, delivered 9, refunded `None` | call on `[a]`, then on `[b]` | `True`, then `False` (None = 0) | pass |
| SM-DLV-08 | R3 | happy | delivery lines X (10/10/0) and Y (10/9/0) | `[X, Y]` | returns `False` | pass |
| SM-DLV-09 | R1 | happy | delivery line 10/10/0; non-delivery line 10/0/0 | call | returns `True` | pass |

## `all_fulfilment_items_fulfilled`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-FUL-01 | R2 | boundary | — | `[]` | returns `True` | pass |
| SM-FUL-02 | R1, R2 | boundary | two `requires_delivery=True` lines, 10/0/0 | call | returns `True` | pass |
| SM-FUL-03 | R1 | boundary | non-delivery line ordered 10, delivered 8, refunded 2 | call | returns `True` | pass |
| SM-FUL-04 | R1 | boundary | non-delivery line 10/7/2 | call | returns `False` | pass |
| SM-FUL-05 | R1 | boundary | (a) non-delivery 10/10/`None`; (b) 10/9/`None` | `[a]`, then `[b]` | `True`, then `False` | pass |
| SM-FUL-06 | R1 | happy | non-delivery 5/5/0 and 5/6/0; delivery line 10/0/0 | call | returns `True` | pass |

## `SalesManager.create_sales_order_with_items`
Default call:
- `order_data = {"account_id": A1, "factory_id": F1, "order_date": date(2026,9,1), "contact_name": "Rahim", "total_amount": Decimal("999.00")}`;
- `items_data = [{"item_id": I1, "quantity_ordered": Decimal("10"), "unit_price": Decimal("5.00"), "line_total": Decimal("51.00")}, {"item_id": None, "description": "Installation work", "quantity_ordered": Decimal("2"), "unit_price": Decimal("50.00"), "line_total": Decimal("100.00"), "requires_delivery": False}]`;
- `workspace_id = W1`, `user_id = U1`.

W1 has no orders unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-CO-01 | R4, R5 | happy | P1 absent | default call | Returns a `SalesOrder` with an id. Re-read the row: `account_id` A1, `factory_id` F1, `order_date` 2026-09-01, `contact_name` "Rahim", `workspace_id` W1, `created_by` U1, `current_status_id` 10, `sales_order_number == f"SO-{Y}-001"`, `total_amount == 999.00` (not the line sum). These are `False`: `order_info_confirmed`, `items_confirmed`, `invoice_confirmed`, `order_completed`, `is_fully_delivered`, `is_invoiced`, `paid`. These are null: `required_approvals`, `invoice_id`, `completed_at`, `completed_by`, `expected_delivery_date`, `description`. | pass |
| SM-CO-02 | R8 | side-effect | as CO-01 | default call | Exactly 2 `sales_order_items` rows for the order, both in W1. Line 1: item I1, qty 10, price 5.00, `line_total == 51.00` (not recomputed), `requires_delivery True`. Line 2: item null, description "Installation work", `requires_delivery False`, `line_total 100.00`. Both lines: delivered = returned = refunded = 0 and `fulfillment_completion_code` null. | pass |
| SM-CO-03 | R6 | side-effect | as CO-01 | default call | Exactly 1 approver row for the order: `user_id` U1, `assigned_by` U1, `approved False`, `approved_at` null, `assigned_at` in range | pass |
| SM-CO-04 | R7 | side-effect | as CO-01 | default call | Exactly 1 event for the order: `event_type 'created'`, description `'Order created'`, `performed_by` U1, metadata null, workspace W1 | pass |
| SM-CO-05 | R4 | boundary | — | default call with `total_amount` removed from `order_data` | re-read `total_amount == 0` | pass |
| SM-CO-06 | R9 | side-effect | — | default call, keeping a reference to the `items_data` list | Each of the caller's two dicts now has `"sales_order_id" == order.id` and `"workspace_id" == W1` | pass |
| SM-CO-07 | R1 | error | — | `items_data=[]` | raises `ValueError`, message `"Sales order must have at least one item"`; NW (no order, approver, event or line) | pass |
| SM-CO-08 | R1 | error | — | `items_data=None` | same `ValueError` and message; NW | pass |
| SM-CO-09 | R2 | error | — | `items_data` = two lines both `item_id` I1 (qty 1, other fields valid) | raises `HTTPException` 409, detail `"Bolt M10 appears more than once on this order"`; NW | pass |
| SM-CO-10 | R2 | boundary | — | two free-text lines "Crate" and "Crate" (both `item_id` None) | order created with 2 lines | pass |
| SM-CO-12 | R3 | error | P1 with `min_order_qty = 5` | one line I1, `quantity_ordered=Decimal("4")` | raises `HTTPException` 422, detail `"Minimum order quantity for Bolt M10 is 5 (requested 4)"`; NW | pass |
| SM-CO-13 | R3 | boundary | P1 `min_order_qty = 5` | one line I1, qty `Decimal("5")` | order created; 1 line with qty 5 | pass |
| SM-CO-14 | R3 | boundary | P1 `min_order_qty` null | one line I1, qty `Decimal("1")` | order created | pass |
| SM-CO-15 | R3 | boundary | P1 `min_order_qty = 0` | one line I1, qty `Decimal("1")` | order created | pass |
| SM-CO-16 | R3 | isolation | P1 with `is_available_for_sale = False`, `min_order_qty = 5`; no other product for F1/I1 | one line I1, qty `Decimal("1")` | order created (a non-sellable product does not apply) | pass |
| SM-CO-17 | R3 | isolation | product for (W1, **F2**, I1), sellable, `min_order_qty = 5`; none for F1 | one line I1, qty `Decimal("1")`, factory F1 | order created | pass |
| SM-CO-18 | R2, R3 | error | P1 `min_order_qty = 5` | two lines I1 each qty `Decimal("1")` | 409 duplicate detail (R2 runs before R3), not 422; NW | pass |
| SM-CO-19 | R10 | error | — | line 1 valid I1 line; line 2 = `{"item_id": None, "description": "X", "quantity_ordered": Decimal("1"), "unit_price": Decimal("1")}` (no `line_total`) | Raises `pydantic.ValidationError`. In the session: 1 new order, 1 approver, 1 `created` event and exactly 1 line (line 1) for that order | pass |
| SM-CO-20 | R10 | error | — | one line `{"item_id": None, "description": "   ", "quantity_ordered": Decimal("1"), "unit_price": Decimal("1"), "line_total": Decimal("1")}` | raises `pydantic.ValidationError`; the new order has 0 lines | pass |
| SM-CO-21 | R11 | error | — | `items_data = [SimpleNamespace(item_id=None, description="X", quantity_ordered=Decimal("1"), unit_price=Decimal("1"), line_total=Decimal("1"))]` | raises `TypeError` | pass |
| SM-CO-22 | Errors "invalid order data" | error | — | default call with `order_date` removed from `order_data` | Raises `pydantic.ValidationError`. NW: no order, approver, event or line. | pass |
| SM-CO-23 | R5 | happy | W1 has 3 orders of Y: `SO-Y-001..003` | default call | `sales_order_number == f"SO-{Y}-004"` | pass |
| SM-CO-24 | R5 | boundary | W1 has 9 orders of Y (`001..009`) | default call | `f"SO-{Y}-010"` | pass |
| SM-CO-25 | R5 | boundary | W1 has 99 orders of Y (`001..099`) | default call | `f"SO-{Y}-100"` | pass |
| SM-CO-26 | R5 | boundary | W1 has 999 orders of Y (`001..999`, bulk insert) | default call | `f"SO-{Y}-1000"` | pass |
| SM-CO-27 | R5 | boundary | W1 has `SO-{Y-1}-001`, `SO-{Y-1}-002` | default call | `f"SO-{Y}-001"` (earlier years are not counted) | pass |
| SM-CO-28 | R5 | isolation | W1 has `SO-Y-001..003`; W2 has 5 orders `SO-Y-101..105` | default call in W1 | `f"SO-{Y}-004"` (W2 is not counted) | pass |
| SM-CO-29 | R5 [BUG-726] | bug | W2 has one order `SO-Y-001`; W1 has none | default call in W1 | no exception; re-read W1 order `sales_order_number == f"SO-{Y}-001"`; W2's order unchanged | xfail BUG-726 — fails today on: `IntegrityError` at flush (global unique index) |
| SM-CO-30 | R12 [BUG-728] | bug | — | `account_id = AX` (W2) | raises `HTTPException` 404, detail `f"Account with ID {AX.id} not found"`; NW | xfail BUG-728 — fails today on: no exception, order created |
| SM-CO-31 | R12 [BUG-728] | bug | — | `account_id = AD` (soft-deleted) | 404, detail `f"Account with ID {AD.id} not found"`; NW | xfail BUG-728 — fails today on: order created |
| SM-CO-32 | R12 [BUG-728] | bug | — | `account_id = 999999999` (no such account) | 404, detail `"Account with ID 999999999 not found"`; NW | xfail BUG-728 — fails today on: `IntegrityError` instead of `HTTPException` |
| SM-CO-33 | R12 [BUG-728] | bug | — | `factory_id = FX` | 404, detail `f"Factory with ID {FX.id} not found"`; NW | xfail BUG-728 — fails today on: order created |
| SM-CO-34 | R12 [BUG-728] | bug | — | `factory_id = FD` | 404, detail `f"Factory with ID {FD.id} not found"`; NW | xfail BUG-728 — fails today on: order created |
| SM-CO-35 | R12 [BUG-728] | bug | — | `items_data` = one line `item_id` IX | 404, detail `f"Item with ID {IX.id} not found"`; NW | xfail BUG-728 — fails today on: order created |
| SM-CO-36 | R12 [BUG-728] | bug | — | one line `item_id` ID (inactive) | 404, detail `f"Item with ID {ID.id} not found"`; NW | xfail BUG-728 — fails today on: order created |
| SM-CO-37 | R12 [BUG-729] | bug | — | `account_id = A2` (supplier only) | raises `HTTPException` 400, detail `"Selected account is not a client"`; NW | xfail BUG-729 — fails today on: order created |
| SM-CO-38 | R13 | boundary | schema | `SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("0.01"), unit_price=Decimal("0"))`; then `quantity_ordered=Decimal("9999999999999.99"), unit_price=Decimal("9999999999999.99")` | both build with no error; values kept | pass |
| SM-CO-39 | R13 [BUG-362] | bug | schema | `SalesOrderItemInput(item_id=1, quantity_ordered=Decimal("0"), unit_price=Decimal("5"))` | raises `ValidationError` naming `quantity_ordered` | xfail BUG-362 — fails today on: no error |
| SM-CO-40 | R13 [BUG-362] | bug | schema | same with `quantity_ordered=Decimal("-5")` | `ValidationError` on `quantity_ordered` | xfail BUG-362 — fails today on: no error |
| SM-CO-41 | R13 [BUG-362] | bug | schema | `quantity_ordered=Decimal("1")`, `unit_price=Decimal("-0.01")` | `ValidationError` on `unit_price` | xfail BUG-362 — fails today on: no error |
| SM-CO-42 | R13 [BUG-021] | bug | schema | `quantity_ordered=Decimal("1.005")`, `unit_price=Decimal("10")` | `ValidationError` on `quantity_ordered` | xfail BUG-021 — fails today on: no error |
| SM-CO-43 | R13 [BUG-021] | bug | schema | `quantity_ordered=Decimal("1")`, `unit_price=Decimal("10.001")` | `ValidationError` on `unit_price` | xfail BUG-021 — fails today on: no error |
| SM-CO-44 | R13 [BUG-021] | bug | schema | `quantity_ordered=Decimal("10000000000000")` (14 integer digits), `unit_price=Decimal("1")` | `ValidationError` on `quantity_ordered` | xfail BUG-021 — fails today on: no error |
| SM-CO-45 | R13 [BUG-021] | bug | schema | `quantity_ordered=Decimal("1")`, `unit_price=Decimal("10000000000000")` | `ValidationError` on `unit_price` | xfail BUG-021 — fails today on: no error |
| SM-CO-46 | R12 [BUG-729] | bug | — | `account_id = A3` (its only `client` tag is inactive) | raises `HTTPException` 400, detail `"Selected account is not a client"`; NW | xfail BUG-729 — fails today on: order created |
| SM-CO-47 | R13 [BUG-362] | bug | — | default call, but line 2's `quantity_ordered = Decimal("-1")`, `line_total = Decimal("-50.00")` (line 1 valid) | raises `pydantic.ValidationError`; NW: no order, approver, event or line, because every line is validated before the order is written | xfail BUG-362 — fails today on: no error, order stored with a −1 line |
| SM-CO-48 | R13 [BUG-021] | bug | — | default call, but line 2's `unit_price = Decimal("50.001")` (line 1 valid) | raises `pydantic.ValidationError`; NW | xfail BUG-021 — fails today on: no error, price rounded on storage |
| SM-CO-49 | R1, R12 | error | — | `account_id = AX`, `items_data = []` | raises `ValueError("Sales order must have at least one item")`, not `HTTPException` (R1 runs before R12); NW | pass |
| SM-CO-50 | R12, R2a [BUG-728], R2 | bug | — | two lines both `item_id` IX (W2 item), qty 1, other fields valid | raises `HTTPException` 404, detail `f"Item with ID {IX.id} not found"` (R12 runs before R2's 409); NW | xfail BUG-728 — fails today on: 409 duplicate raised instead of 404 |
| SM-CO-51 | Inputs `factory_id` key (G10) | error | — | default call with the `factory_id` key removed from `order_data` | raises `KeyError`, `exc.args == ("factory_id",)`; NW | pass |
| SM-CO-52 | R12 [BUG-728] | bug | — | `account_id = AX`, `factory_id = FX`, line 1 `item_id` IX | 404, detail `f"Account with ID {AX.id} not found"` (account checked first); NW | xfail BUG-728 — fails today on: no exception |
| SM-CO-53 | R12 [BUG-728, BUG-729] | bug | — | `account_id = A2` (supplier only), `factory_id = FX` | 400, detail `"Selected account is not a client"` (client tag checked before factory); NW | xfail BUG-729 — fails today on: order created |

## `SalesManager.create_delivery_with_items`
Setup unless stated:
- SO1 with `invoice_confirmed = True` and lines LA, LB, LB2, LS. DM1 exists.
- W1 has no deliveries of year Y.

Default call:
- `delivery_data = {"sales_order_id": SO1, "delivery_method_id": DM1, "scheduled_date": date(2026,10,5), "tracking_number": "TRK-100", "notes": "Gate 3"}`;
- `workspace_id = W1`, `user_id = U1`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-CD-01 | R4, R9, R12 | happy | default | items `[{"sales_order_item_id": LA, "quantity_delivered": Decimal("4"), "notes": "fragile"}, {"sales_order_item_id": LB, "quantity_delivered": Decimal("2.50")}]` | Returns a tuple `(delivery, order)` with `order.id == SO1.id`. Re-read the delivery: `sales_order_id` SO1, `delivery_method_id` DM1, `scheduled_date` 2026-10-05, `tracking_number` "TRK-100", `notes` "Gate 3", `workspace_id` W1, `created_by` U1, `delivery_status 'planned'`, `delivery_number == f"DEL-{Y}-001"`. Exactly 2 delivery lines: (LA, `item_id` I1, qty 4, notes "fragile", W1) and (LB, `item_id` null, qty 2.50, notes null, W1). LA and LB still have delivered 0.00 and refunded 0.00 (R12). | pass |
| SM-CD-02 | R11 | side-effect | default | as CD-01 | Exactly 1 new event on SO1: `'delivery_planned'`, description `f"Delivery DEL-{Y}-001 planned (6.50 units across 2 items)"`, metadata `{"delivery_id": <new id>, "tracking_number": "TRK-100"}`, `performed_by` U1 | pass |
| SM-CD-03 | R11 | boundary | default | `delivery_data` without `tracking_number`; items `[{LA, Decimal("1")}]` | description `f"Delivery DEL-{Y}-001 planned (1 unit across 1 item)"`; metadata `{"delivery_id": id, "tracking_number": None}` | pass |
| SM-CD-04 | R11 | boundary | default | items `[{LA, Decimal("2")}]` | description ends `"(2 units across 1 item)"` | pass |
| SM-CD-05 | R11 | boundary | default | items `[{LB, Decimal("0.50")}, {LB2, Decimal("0.50")}]` | description ends `"(1.00 unit across 2 items)"` | pass |
| SM-CD-06 | R1 | error | default | items `[]` | `ValueError("Delivery must have at least one item")`; NW | pass |
| SM-CD-07 | R2 | error | default | `sales_order_id = 999999999` | `ValueError("Sales order 999999999 not found")`; NW | pass |
| SM-CD-08 | R2 | isolation | SOX = an order in W2 (number "SO-2026-900", invoice confirmed) with a delivery line | `sales_order_id = SOX`, W1 | `ValueError(f"Sales order {SOX.id} not found")`; NW | pass |
| SM-CD-09 | R3 | error | SO1 `invoice_confirmed = False` | items `[{LA, Decimal("1")}]` | `ValueError("Finalize the invoice before planning a delivery")`; NW | pass |
| SM-CD-10 | R5, R10 | error | default | items `[{"sales_order_item_id": 999999999, "quantity_delivered": Decimal("1")}]` | `ValueError("Sales order item 999999999 not found")`. In the session: no delivery lines and no `delivery_planned` event. Whether a delivery row was flushed is not asserted: R10a lets a fix move this check ahead of the insert. | pass |
| SM-CD-11 | R5 | isolation | LX = a line of an order in W2 | items `[{LX, Decimal("1")}]` | `ValueError(f"Sales order item {LX.id} not found")`; no delivery lines, no event | pass |
| SM-CD-12 | R5 [BUG-723] | bug | SO2 = second W1 order "SO-2026-012", invoice confirmed, with line L2 (catalog I1, ordered 10.00) | items `[{L2, Decimal("1")}]` on SO1 | `ValueError(f"Sales order item {L2.id} does not belong to sales order {SO1.id}")`; no delivery of SO1 exists; no delivery lines; no event; L2 unchanged | xfail BUG-723 — fails today on: no error raised |
| SM-CD-13 | R6 | error | default | items `[{LS, Decimal("1")}]` | `ValueError(f"Sales order item {LS.id} does not require delivery — it should be fulfilled directly, not delivered")`; no delivery lines, no event | pass |
| SM-CD-14 | R10 | error | default | items `[{LA, Decimal("2")}, {LS, Decimal("1")}]` | Raises the R6 `ValueError` with the exact LS message. In the session there is no `delivery_planned` event and no delivery line for LS. If SO1 has a delivery (today: yes), it has exactly 1 line (LA, 2.00). If SO1 has no delivery, there are 0 delivery lines (R10a allows this). | pass |
| SM-CD-15 | R7 | error | LA delivered `3.00`, refunded `1.00`; D0 = planned delivery `DEL-2026-001` with `DL(LA, 2.00)` | items `[{LA, Decimal("5")}]` | `ValueError(f"Cannot plan 5 unit(s) for sales order item {LA.id} — only 4.00 unit(s) are available to plan (2.00 already committed to other planned deliveries). Edit or delete an existing planned delivery to free up capacity.")`; no new delivery lines, no new event | pass |
| SM-CD-16 | R7 | boundary | as CD-15 | items `[{LA, Decimal("4")}]` | accepted; new delivery line (LA, 4) | pass |
| SM-CD-17 | R7 | boundary | LA delivered 0; deliveries of SO1: `DEL-2026-001` `delivered` with `DL(LA, 2.00)`, `DEL-2026-002` `cancelled` with `DL(LA, 3.00)`, `DEL-2026-003` status `"shipped"` with `DL(LA, 1.00)` | items `[{LA, Decimal("10")}]` | accepted (only `planned` deliveries count); exactly 1 new delivery line (LA, 10) | pass |
| SM-CD-18 | R7 | boundary | LB delivered `6.00` (over ordered 5.00) | items `[{LB, Decimal("1")}]` | `ValueError(f"Cannot plan 1 unit(s) for sales order item {LB.id} — only 0 unit(s) are available to plan (0 already committed to other planned deliveries). Edit or delete an existing planned delivery to free up capacity.")` (floor at 0, renders `0`); no delivery lines, no event | pass |
| SM-CD-19 | R7a [BUG-720] | bug | default; SQL capture on | items `[{LA, Decimal("1")}]` | returns a tuple; captured SQL locks `sales_order_items` before the first INSERT into `sales_delivery_items` (a lock on the order lines; a lock on `sales_orders` alone does not count) | xfail BUG-720 — fails today on: no captured SELECT on `sales_order_items` contains `FOR UPDATE` |
| SM-CD-20 | R8 [BUG-724] | bug | default | items `[{LA, Decimal("6")}, {LA, Decimal("6")}]` | `ValueError(f"Sales order item {LA.id} appears more than once in this delivery")`; no delivery of SO1; no delivery lines; no event | xfail BUG-724 — fails today on: no error raised (12 planned for 10 ordered) |
| SM-CD-21 | R8 [BUG-724] | bug | default | items `[{LA, Decimal("2")}, {LA, Decimal("3")}]` (within capacity) | `ValueError(f"Sales order item {LA.id} appears more than once in this delivery")`; no delivery of SO1; no delivery lines; no event | xfail BUG-724 — fails today on: no error raised |
| SM-CD-22 | R4 [BUG-722] | bug | default | `delivery_data` plus `"delivery_status": "delivered"`; items `[{LA, Decimal("1")}]` | no error; re-read `delivery_status == 'planned'` | xfail BUG-722 — fails today on: status stored as `'delivered'` |
| SM-CD-23 | R4 [BUG-722] | bug | default | `delivery_data` plus `"delivery_status": "draft"`; items `[{LA, Decimal("8")}]`; then a second call with items `[{LA, Decimal("8")}]` | First call stored as `'planned'`. The second call raises the R7 capacity `ValueError`. | xfail BUG-722 — fails today on: first status `'draft'`, second call accepted |
| SM-CD-24 | R4 | happy | W1 has `DEL-Y-001`, `DEL-Y-002` (deliveries of SO1, cancelled); `DEL-{Y-1}-001` in W1; W2 has `DEL-Y-101..103` | items `[{LA, Decimal("1")}]` | `delivery_number == f"DEL-{Y}-003"` | pass |
| SM-CD-25 | R4 [BUG-726] | bug | W2 has a delivery `DEL-Y-001`; W1 has none | items `[{LA, Decimal("1")}]` | no exception; W1 delivery number `f"DEL-{Y}-001"` | xfail BUG-726 — fails today on: `IntegrityError` at flush |
| SM-CD-26 | R13 [BUG-725] | bug | default | items `[{LA, Decimal("2.5")}]` (catalog line) | raises a plain `ValueError` (not a pydantic `ValidationError`) with `str(exc) == "Delivery line has a fractional quantity; stock requires whole units"`; no delivery of SO1; no delivery lines; no event | xfail BUG-725 — fails today on: no error raised |
| SM-CD-27 | R13 | boundary | default | items `[{LA, Decimal("3.00")}]` | accepted; line qty 3 | pass |
| SM-CD-28 | R13 | boundary | default | items `[{LB, Decimal("2.5")}]` (free text) | accepted; line qty 2.5 | pass |
| SM-CD-29 | R13 [BUG-730] | bug | default | `delivery_method_id = DMX`; items `[{LA, Decimal("1")}]` | `ValueError(f"Delivery method {DMX.id} not found")`; no delivery of SO1; no lines; no event | xfail BUG-730 — fails today on: delivery created |
| SM-CD-30 | R13 [BUG-730] | bug | default | `delivery_method_id = DMD` | `ValueError(f"Delivery method {DMD.id} not found")`; no delivery of SO1 | xfail BUG-730 — fails today on: delivery created |
| SM-CD-31 | R13 | happy | default | `delivery_method_id = DM2`; items `[{LA, Decimal("1")}]` | accepted; re-read `delivery_method_id == DM2` | pass |
| SM-CD-32 | R13 | boundary | schema | `SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("0.01"))`; then `Decimal("9999999999999.99")` | both build with no error | pass |
| SM-CD-33 | R13 [BUG-362] | bug | schema | `SalesDeliveryItemInput(sales_order_item_id=1, quantity_delivered=Decimal("0"))` | `ValidationError` on `quantity_delivered` | xfail BUG-362 — fails today on: no error |
| SM-CD-34 | R13 [BUG-362] | bug | schema | `quantity_delivered=Decimal("-3")` | `ValidationError` | xfail BUG-362 — fails today on: no error |
| SM-CD-35 | R13 [BUG-021] | bug | schema | `quantity_delivered=Decimal("1.005")` | `ValidationError` | xfail BUG-021 — fails today on: no error |
| SM-CD-36 | R13 [BUG-021] | bug | schema | `quantity_delivered=Decimal("10000000000000")` | `ValidationError` | xfail BUG-021 — fails today on: no error |
| SM-CD-37 | R7 | isolation | D0 = planned delivery of SO1 with `DL(LB, 4.00)` (LB ordered 5.00) | items `[{LA, Decimal("10")}]` | accepted (another line's planned quantity does not reduce LA) | pass |
| SM-CD-38 | R4 [BUG-722] | bug | schema | `SalesDeliveryCreate(sales_order_id=1, delivery_method_id=1, delivery_status="cancelled")` | builds with no error (the extra key is ignored); `"delivery_status" not in obj.model_dump()` | xfail BUG-722 — fails today on: dump contains `delivery_status == 'cancelled'` |
| SM-CD-39 | R11 | boundary | default | items `[{LA, Decimal("1")}, {LB, Decimal("1")}]` | description ends `"(2 units across 2 items)"` | pass |
| SM-CD-40 | R9 | side-effect | default | items `[{LB, Decimal("1"), "notes": None}]` | delivery line `item_id` null, `notes` null, `sales_order_item_id` LB, `workspace_id` W1 | pass |
| SM-CD-41 | R2 | isolation | default | call with `workspace_id = W2`, `user_id = U5` | `ValueError(f"Sales order {SO1.id} not found")`; NW | pass |
| SM-CD-43 | R10 | error | default; P1 exists | items `[{LA, Decimal("1")}, {LA, Decimal("100")}]` | Raises `ValueError` (R7 capacity today, R8 after the fix). No `delivery_planned` event in the session. | pass |
| SM-CD-44 | R13, R10a [BUG-362] | bug | default | items `[{LA, Decimal("1")}, {LB, Decimal("0")}]` | raises `pydantic.ValidationError`; no delivery of SO1; no delivery lines; no event | xfail BUG-362 — fails today on: no error raised (0 planned) |
| SM-CD-45 | R13, R10a [BUG-021] | bug | default | items `[{LB, Decimal("1.005")}]` | raises `pydantic.ValidationError`; no delivery of SO1; no delivery lines; no event | xfail BUG-021 — fails today on: no error raised |
| SM-CD-46 | R5, R10a [BUG-723] | bug | SO2 and L2 as in CD-12 | items `[{LA, Decimal("1")}, {L2, Decimal("1")}]` on SO1 | `ValueError(f"Sales order item {L2.id} does not belong to sales order {SO1.id}")`; no delivery of SO1 (the whole request is checked before the delivery row); no delivery lines; no event | xfail BUG-723 — fails today on: no error raised |

## `SalesManager.complete_delivery`
Setup unless stated:
- SO1 (`sales_order_number "SO-2026-010"`, A1, F1, `invoice_confirmed True`) with LA and LB.
- P1 (qty 20, average cost 4.00).
- D1 = `DEL-2026-004`, planned, lines `DL(LA, 4.00)` and `DL(LB, 2.00)`.

Default call: `(D1, W1, U1, actual_delivery_date=date(2026,9,29), completion_code="OK-77")`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-CPD-01 | R3, R4 | happy | default | default call | Returns SO1 (same id). Re-read D1: `delivery_status 'delivered'`, `actual_delivery_date` 2026-09-29, `completion_code "OK-77"`. LA delivered `4.00`; LB delivered `2.00`. | pass |
| SM-CPD-02 | R5, R6 | side-effect | default | default call | P1 `qty == 16`, `updated_by` U1. Exactly one new product-ledger row, with:<br>- `transaction_type 'sale'`, quantity 4, `qty_before 20`, `qty_after 16`;<br>- `unit_cost 4.00`, `total_cost 16.00`, `avg_cost_before == avg_cost_after == 4.00`;<br>- `source_type 'sales_delivery'`, `source_id` D1, `transfer_destination_type 'customer'`, `transfer_destination_id` A1;<br>- `performed_by` U1;<br>- notes start with `"Delivery DEL-2026-004 for "` and end with `"SO-2026-010"`.<br>No ledger row for LB. | pass |
| SM-CPD-03 | R5 [BUG-735] | bug | default | default call | ledger row notes `== "Delivery DEL-2026-004 for SO-2026-010"` | xfail BUG-735 — fails today on: notes `"… for SO-SO-2026-010"` |
| SM-CPD-04 | R5 | boundary | P1 average cost null | default call | ledger row `unit_cost` null and `total_cost` null; P1 qty 16 | pass |
| SM-CPD-05 | R9 | side-effect | default | default call | Exactly 1 new event on SO1: `'delivery_completed'`, description `"Delivery DEL-2026-004 marked delivered on 2026-09-29 (code: OK-77)"`, metadata `{"delivery_id": D1, "actual_delivery_date": "2026-09-29", "completion_code": "OK-77"}`, `performed_by` U1 | pass |
| SM-CPD-06 | R3, R9 | boundary | default | `actual_delivery_date=None`, `completion_code=None` | D1 `actual_delivery_date == date.today()`; event description `f"Delivery DEL-2026-004 marked delivered on {today.isoformat()}"` with no `"(code:"`; metadata `completion_code` null, `actual_delivery_date == today.isoformat()`; D1 `completion_code` null | pass |
| SM-CPD-07 | R3, R9 [BUG-734] | bug | default | `completion_code="   "` | D1 `completion_code` null; description contains no `"(code:"`; metadata `completion_code` null | xfail BUG-734 — fails today on: stored `"   "` |
| SM-CPD-08 | R3 [BUG-734] | bug | default | `completion_code=""` | D1 `completion_code` null; description has no `"(code:"` | xfail BUG-734 — fails today on: stored `""` |
| SM-CPD-09 | R3, R9 [BUG-734] | bug | default | `completion_code="  OK-77  "` | D1 `completion_code == "OK-77"`; description ends `"(code: OK-77)"`; metadata `completion_code "OK-77"` | xfail BUG-734 — fails today on: stored untrimmed |
| SM-CPD-10 | R3 [BUG-734] | bug | D1 `completion_code = "OLD"` | `completion_code=None` | D1 `completion_code` null | xfail BUG-734 — fails today on: still `"OLD"` |
| SM-CPD-11 | R3 [BUG-733] | bug | D1 `updated_by` null | default call | re-read D1 `updated_by == U1` | xfail BUG-733 — fails today on: `updated_by` null |
| SM-CPD-12 | R8 | side-effect | SO1 only LA (delivered 6.00) and LB (delivered 3.00); `is_fully_delivered False` | default call | SO1 `is_fully_delivered True` | pass |
| SM-CPD-13 | R8 | side-effect | default (LA ends at 4 of 10) | default call | SO1 `is_fully_delivered False` | pass |
| SM-CPD-14 | R1 | error | default | `delivery_id=999999999` | `ValueError("Delivery not found")`; NW | pass |
| SM-CPD-15 | R1 | isolation | default | D1 with `workspace_id=W2` | `ValueError("Delivery not found")`; NW (D1 still planned, P1 20) | pass |
| SM-CPD-16 | R2 [BUG-721] | bug | D1 status `delivered` | default call | `ValueError("Only planned deliveries can be completed (this delivery is 'delivered')")`; NW: LA, LB delivered 0.00; P1 qty 20; no ledger row; no event | xfail BUG-721 — fails today on: no error, quantities added again |
| SM-CPD-17 | R2 [BUG-721] | bug | D1 status `cancelled` | default call | `ValueError("Only planned deliveries can be completed (this delivery is 'cancelled')")`; NW | xfail BUG-721 — fails today on: stock deducted |
| SM-CPD-18 | R2a [BUG-720] | bug | default; SQL capture on | default call | returns SO1; captured SQL locks `sales_deliveries` before the first UPDATE of `sales_order_items` | xfail BUG-720 — fails today on: no captured SELECT on `sales_deliveries` contains `FOR UPDATE` |
| SM-CPD-19 | R4 | boundary | LA delivered `9.00`; D1 only `DL(LA, 4.00)` | default call | LA delivered `13.00` (no cap) | pass |
| SM-CPD-20 | R7 | error | D1 only `DL(LA, 0.00)` | default call | `ValueError("Sale deduction quantity must be positive")`; P1 qty 20; no ledger row | pass |
| SM-CPD-21 | R7 | error | D1 only `DL(LA, 2.50)` | default call | `HTTPException` 400, detail `"Delivery line has a fractional quantity; stock requires whole units"`; P1 20; no ledger row | pass |
| SM-CPD-22 | R7 | error | P1 absent; D1 only `DL(LA, 4.00)` | default call | `HTTPException` 422, detail `f"Insufficient sellable stock for item {I1.id} at factory {F1.id}: requested 4, available 0"`. No ledger row. In the session, D1 is already `delivered` (flushed before the stock step). | pass |
| SM-CPD-23 | R7 | error | P1 qty 3; D1 only `DL(LA, 4.00)` | default call | 422, detail `f"Insufficient sellable stock for item {I1.id} at factory {F1.id}: requested 4, available 3"`; P1 qty 3; no ledger row | pass |
| SM-CPD-24 | R7 | boundary | P1 qty 4; D1 only `DL(LA, 4.00)` | default call | success; P1 qty 0; ledger `qty_after 0` | pass |
| SM-CPD-25 | R5, R7 | isolation | P1 `is_available_for_sale = False`, qty 20; product (W1, **F2**, I1) sellable qty 20; D1 only `DL(LA, 4.00)` | default call | 422, detail `f"Insufficient sellable stock for item {I1.id} at factory {F1.id}: requested 4, available 0"`; both products qty 20; no ledger row | pass |
| SM-CPD-26 | R10 | boundary | D1 with no lines | default call | Returns SO1. D1 `delivered`. One `delivery_completed` event. No ledger rows. SO1 `is_fully_delivered` recomputed: `False` (LA, LB undelivered). | pass |
| SM-CPD-27 | R11 | happy | SO1 `invoice_confirmed = False` | default call | success; D1 `delivered`; P1 16 | pass |
| SM-CPD-28 | R6 | happy | D1 only `DL(LB, 2.00)` | default call | LB delivered 2.00; P1 qty 20, `updated_by` unchanged; no ledger row | pass |

## `SalesManager.cancel_delivery`
Setup: SO1 with LA (ordered 10.00), P1 qty 20, and D1 planned with `DL(LA, 6.00)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-CAN-01 | R3, R4 | happy | default | `(D1, W1, user_id=U1)` | Returns D1 (same id). Re-read: status `'cancelled'`; tracking "TRK-100", notes "Gate 3", scheduled 2026-10-05, method DM1 unchanged; LA delivered 0.00; P1 qty 20; no ledger row. One event on SO1: `'delivery_cancelled'`, `"Delivery DEL-2026-004 cancelled"`, metadata `{"delivery_id": D1}`, `performed_by` U1. | pass |
| SM-CAN-02 | R3 | side-effect | default; SO1 invoice confirmed | cancel D1; then `create_delivery_with_items` for SO1 with `[{LA, Decimal("10")}]` | the second call succeeds (the cancelled 6 no longer count as planned) | pass |
| SM-CAN-03 | R4 | boundary | default | `user_id=None` | event `performed_by` null | pass |
| SM-CAN-04 | R1 | error | default | `delivery_id=999999999` | `ValueError("Delivery 999999999 not found")`; NW | pass |
| SM-CAN-05 | R1 | isolation | default | D1 with `workspace_id=W2` | `ValueError(f"Delivery {D1.id} not found")`; NW | pass |
| SM-CAN-06 | R2 | error | D1 status `delivered` | cancel | `ValueError("Only planned deliveries can be cancelled (this delivery is 'delivered')")`; NW | pass |
| SM-CAN-07 | R2 | boundary | D1 status `cancelled`; then a second setup with status `"Planned"` | cancel each | `… (this delivery is 'cancelled')` / `… (this delivery is 'Planned')`; NW each | pass |
| SM-CAN-08 | R3 [BUG-733] | bug | default | cancel with U1 | D1 `updated_by == U1` | xfail BUG-733 — fails today on: `updated_by` null |
| SM-CAN-09 | R2a [BUG-720] | bug | default; SQL capture on | cancel with U1 | returns D1; captured SQL locks `sales_deliveries` before the first UPDATE of `sales_deliveries` | xfail BUG-720 — fails today on: no `FOR UPDATE` on `sales_deliveries` |

## `SalesManager.update_delivery`
Setup:
- D1 planned: `scheduled_date` 2026-10-05, DM1, tracking "TRK-100", notes "Gate 3", `updated_by` U2.
- `data` is a `SalesDeliveryEditRequest` built with only the fields named.

Call: `(D1, W1, data, user_id=U1)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-UD-01 | R3, R4 | happy | default | `scheduled_date=2026-10-07, delivery_method_id=DM2, tracking_number="TRK-200", notes="Gate 5"` | Returns D1. Re-read the four new values. One event: `'delivery_updated'`, `"Delivery DEL-2026-004 updated (scheduled date, delivery method, tracking number, notes)"`, metadata `{"delivery_id": D1}`, `performed_by` U1. | pass |
| SM-UD-02 | R4 | happy | default | `tracking_number="TRK-100"` (same), `notes="Gate 9"` | event description `"Delivery DEL-2026-004 updated (notes)"`; tracking still TRK-100 | pass |
| SM-UD-03 | R4 | happy | default | `notes="Gate 9", scheduled_date=2026-10-08` (sent in that order) | description `"… updated (scheduled date, notes)"` (fixed order) | pass |
| SM-UD-04 | R5 | boundary | default | all four fields sent equal to the stored values | returns D1; no event; row unchanged; `updated_by` still U2 | pass |
| SM-UD-05 | R3 | happy | default | `tracking_number="TRK-300"` only | tracking TRK-300; scheduled, method, notes unchanged; description `"… updated (tracking number)"` | pass |
| SM-UD-06 | R3, R4 [BUG-732] | bug | default | `SalesDeliveryEditRequest(tracking_number=None)` | tracking null; one event `"Delivery DEL-2026-004 updated (tracking number)"` | xfail BUG-732 — fails today on: tracking still `"TRK-100"` |
| SM-UD-07 | R3 [BUG-732] | bug | default | `SalesDeliveryEditRequest(scheduled_date=None, notes=None)` | scheduled null, notes null; event `"… updated (scheduled date, notes)"`; tracking and method unchanged | xfail BUG-732 — fails today on: values unchanged |
| SM-UD-08 | R3 [BUG-732] | bug | schema | `SalesDeliveryEditRequest(delivery_method_id=None)` | raises `ValidationError` | xfail BUG-732 — fails today on: no error |
| SM-UD-09 | R3 | boundary | schema | `SalesDeliveryEditRequest()`; `SalesDeliveryEditRequest(tracking_number=None)`; `SalesDeliveryEditRequest(delivery_method_id=5)` | all three build | pass |
| SM-UD-10 | R3 [BUG-733] | bug | default | `tracking_number="TRK-300"` | D1 `updated_by == U1` | xfail BUG-733 — fails today on: still U2 |
| SM-UD-11 | R6 | side-effect | default | `data` = an ad-hoc pydantic model with a single field `delivery_status="cancelled"` | Returns D1. Re-read D1 `delivery_status == 'cancelled'`; tracking, notes, scheduled date and method unchanged. Exactly one new event: `'delivery_updated'`, description `"Delivery DEL-2026-004 updated ()"` (the field has no label), metadata `{"delivery_id": D1.id}`, `performed_by` U1. | pass |
| SM-UD-12 | R1 | error | default | `delivery_id=999999999`, `tracking_number="X"` | `ValueError("Delivery 999999999 not found")`; NW | pass |
| SM-UD-13 | R1 | isolation | default | D1, `workspace_id=W2` | `ValueError(f"Delivery {D1.id} not found")`; NW | pass |
| SM-UD-14 | R2 | error | D1 status `delivered` | `tracking_number="X"` | `ValueError("Only planned deliveries can be edited (this delivery is 'delivered')")`; NW | pass |
| SM-UD-15 | R2 | error | D1 status `cancelled` | `notes="X"` | `ValueError("Only planned deliveries can be edited (this delivery is 'cancelled')")`; NW | pass |
| SM-UD-16 | R7 [BUG-730] | bug | default | `delivery_method_id=DMX` | `ValueError(f"Delivery method {DMX.id} not found")`; NW (method still DM1, no event) | xfail BUG-730 — fails today on: DMX stored |
| SM-UD-17 | R7 [BUG-730] | bug | default | `delivery_method_id=DMD` | `ValueError(f"Delivery method {DMD.id} not found")`; NW | xfail BUG-730 — fails today on: DMD stored |
| SM-UD-18 | R4 | boundary | default | `user_id=None`, `notes="Gate 9"` | event `performed_by` null | pass |
| SM-UD-19 | R5 [BUG-733] | boundary | default | `tracking_number="TRK-100"` (same) by U1 | Returns D1. `updated_by` still U2. No event. (Checks that the fix does not stamp a no-op; paired with UD-10.) | pass |
| SM-UD-20 | R3 | happy | default | `delivery_method_id=DM2` only | method DM2; description `"… updated (delivery method)"` | pass |
| SM-UD-21 | R3, R4, R6 | boundary | default (D1 `delivery_status 'planned'`) | `data` = an ad-hoc pydantic model with fields `delivery_status: str = "cancelled"` and `notes: str \| None = None`, built as `Model(notes="Gate 9")` (so `delivery_status` is unset and keeps its default) | Returns D1. Re-read D1: `notes == "Gate 9"`; `delivery_status == 'planned'` (an unset field is not sent, so it is not written); `scheduled_date` 2026-10-05, `delivery_method_id` DM1, `tracking_number` "TRK-100" unchanged. Exactly one new event on SO1: `'delivery_updated'`, description `"Delivery DEL-2026-004 updated (notes)"`, metadata `{"delivery_id": D1.id}`, `performed_by` U1. (Only sent fields count, per R3/R4; R6 applies to sent fields only (best-practice default, delegated by reviewer).) | pass |
| SM-UD-22 | R3, R5, R6 | boundary | default (D1 `delivery_status 'planned'`, notes "Gate 3", `updated_by` U2) | `data` = an ad-hoc pydantic model with fields `delivery_status: str = "cancelled"` and `notes: str \| None = None`, built as `Model(notes="Gate 3")` (the only sent field equals the stored value; `delivery_status` is unset and keeps a default that differs from the stored `'planned'`) | Returns D1. No new event on SO1: the `sales_order_events` row count is unchanged and there is no `'delivery_updated'` event. Re-read D1: `delivery_status == 'planned'`, `notes == "Gate 3"`, `scheduled_date` 2026-10-05, `delivery_method_id` DM1, `tracking_number` "TRK-100", `updated_by` still U2. (An unset field is not sent, so it is neither compared nor written: every sent value equals the stored one, which is the R5 no-op. If unset fields were counted, an event `"Delivery DEL-2026-004 updated ()"` would appear.) | pass |

> SM-UD-19 is a pass case: it holds today, and it must keep holding after BUG-733 is fixed.

## `SalesManager.fulfill_service_item`
Setup:
- SO1 with `invoice_confirmed True` and lines LS, LT, LU, LA.
- LS, LT, LU have delivered 0.00 and refunded 0.00.
- `fulfillment_completion_code` is null.

Call: `(line, W1, U1, completion_code=...)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-FSI-01 | R4, R5, R9 | happy | default | LS, `"C-1"` | Returns SO1. LS delivered `5.00`, `fulfillment_completion_code "C-1"`. One event: `'item_fulfilled'`, `"Installation fulfilled (5.00 hour) (code: C-1)"`, metadata `{"item_id": LS.id, "completion_code": "C-1"}`, `performed_by` U1. No `sales_deliveries` / `sales_delivery_items` rows. P1 (if present) and ledger untouched. | pass |
| SM-FSI-02 | R4, R5 | happy | default | LT, `None` | LT delivered 2.00; code null; description `"Site survey fulfilled (2.00 unit(s))"`; metadata `completion_code` null | pass |
| SM-FSI-03 | R5 | boundary | default | LU, `None` | description `"Calibration fulfilled (3.00 unit(s))"` (empty unit → fallback) | pass |
| SM-FSI-04 | R5 | boundary | line LE = catalog item IE (name `""`), description null, no delivery, ordered 1.00 | LE, `None` | description `f"Item #{IE.id} fulfilled (1.00 unit(s))"` | pass |
| SM-FSI-05 | R6 | boundary | LS delivered 5.00 | LS, `"X"` | returns SO1; LS delivered 5.00, code still null; no event | pass |
| SM-FSI-06 | R6 | boundary | LS delivered 6.00 | LS, `None` | returns SO1; no change; no event | pass |
| SM-FSI-07 | R4 | boundary | LS delivered 2.00 | LS, `None` | delivered 5.00; one event | pass |
| SM-FSI-08 | R6 [BUG-731] | bug | LS delivered 3.00, refunded 2.00 | LS, `None` | returns SO1; delivered still 3.00; no event | xfail BUG-731 — fails today on: delivered becomes 5.00 and an event is logged |
| SM-FSI-09 | R4 [BUG-731] | bug | LS delivered 1.00, refunded 2.00 | LS, `None` | delivered `3.00`; one event | xfail BUG-731 — fails today on: delivered 5.00 |
| SM-FSI-11 | R4, R5 [BUG-734] | bug | default | LS, `"   "` | code null; description `"Installation fulfilled (5.00 hour)"` exactly; metadata `completion_code` null | xfail BUG-734 — fails today on: code stored `"   "` |
| SM-FSI-12 | R4, R5 [BUG-734] | bug | default | LS, `"  C-1 "` | code `"C-1"`; description ends `"(code: C-1)"`; metadata `"C-1"` | xfail BUG-734 — fails today on: untrimmed |
| SM-FSI-13 | R4 | boundary | default | LS, `""` | code null; description `"Installation fulfilled (5.00 hour)"` | pass |
| SM-FSI-14 | R8 | side-effect | SO1 lines only LS (delivered 0) and LA (delivered 10.00); flag `False` | LS | SO1 `is_fully_delivered True` | pass |
| SM-FSI-15 | R8 | side-effect | default (LA undelivered) | LS | flag stays `False` | pass |
| SM-FSI-16 | R1 | error | default | `order_item_id=999999999` | `ValueError("Sales order item 999999999 not found")`; NW | pass |
| SM-FSI-17 | R1 | isolation | default | LS with `workspace_id=W2` | `ValueError(f"Sales order item {LS.id} not found")`; NW | pass |
| SM-FSI-18 | R2 | error | SO1 `invoice_confirmed False` | LA | `ValueError("This line requires delivery — use the delivery workflow, not direct fulfillment")` (R2 before R3); NW | pass |
| SM-FSI-19 | R3 | error | SO1 `invoice_confirmed False` | LS | `ValueError("Finalize the invoice before fulfilling this line")`; NW | pass |
| SM-FSI-20 | R3a [BUG-720] | bug | default; SQL capture on | LS, `None` | returns SO1; captured SQL locks `sales_order_items` before the first UPDATE of `sales_order_items` | xfail BUG-720 — fails today on: no `FOR UPDATE` on `sales_order_items` |

## `SalesManager._recompute_is_fully_delivered`
Call: `(session, SO1, W1)`. Returns bool.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-RFD-01 | R1, R3 | happy | SO1 flag `False`; LA 10/10, LS 5/6 (over), LB 5/5 | call | returns `True`; re-read flag `True` | pass |
| SM-RFD-02 | R1 | boundary | flag `False`; LA 10/9, LS 5/5 | call | returns `False`; flag `False` | pass |
| SM-RFD-03 | R3 | side-effect | flag `True`; LA 10/9 | call | returns `False`; flag `False` | pass |
| SM-RFD-04 | R2 | boundary | SO1 no lines, flag `False` | call | returns `True`; flag `True` | pass |
| SM-RFD-05 | R1 [BUG-731] | bug | flag `False`; LA ordered 10, delivered 8, refunded 2 | call | returns `True`; flag `True` | xfail BUG-731 — fails today on: returns `False` |
| SM-RFD-06 | R1 | isolation | flag `False`; LA 10/10 in W1; a line with `sales_order_id` SO1 but `workspace_id` W2, 10/0 | call with W1 | returns `True` | pass |
| SM-RFD-08 | R3 | boundary | flag `True`; all lines done | call | returns `True`; flag `True` | pass |

## `SalesManager._base_sections_confirmed`
Transient order objects.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-BSC-01 | R1 | happy | info True, items True, invoice False | call | `True` | pass |
| SM-BSC-02 | R1 | boundary | info True, items False, invoice True | call | `False` | pass |
| SM-BSC-03 | R1 | boundary | info False, items True, invoice True | call | `False` | pass |
| SM-BSC-04 | R1 | boundary | info False, items False, invoice True | call | `False` | pass |

## `SalesManager.is_so_financially_locked`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-LCK-01 | R1 | boundary | SO1 `invoice_id` null | call | `False` | pass |
| SM-LCK-02 | R2 | isolation | SO1 linked to `INV('confirmed','unpaid', ws=W2)` | call | `False` | pass |
| SM-LCK-03 | R3 | happy | SO1 linked to `INV('confirmed','unpaid')` | call | `True` | pass |
| SM-LCK-04 | R3 | boundary | `INV('draft','unpaid')` | call | `False` | pass |
| SM-LCK-05 | R3 | boundary | `INV('voided','unpaid')` | call | `False` | pass |

## `SalesManager.unlink_invoice_from_so`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-UNL-01 | R1, R2, R3 | happy | SO1 linked to INV1 = `INV('confirmed','paid')`; `invoice_confirmed`, `is_invoiced`, `paid`, `order_info_confirmed`, `items_confirmed` all True; `AP(SO1, U1, approved True)` | `(SO1, U1, "Invoice voided")` | Returns `None`. SO1: `invoice_id` null; `invoice_confirmed`, `is_invoiced`, `paid` False; `order_info_confirmed`, `items_confirmed` still True. INV1 still exists, status `confirmed`. U1 approver still approved. One event: `'invoice_unlinked'`, `"Invoice voided"`, `performed_by` U1, metadata `{"invoice_id": INV1.id}`. | pass |
| SM-UNL-02 | R2 | happy | as UNL-01 | `(SO1, None, "Draft deleted", event_type='invoice_draft_deleted')` | event type `'invoice_draft_deleted'`, description "Draft deleted", `performed_by` null | pass |
| SM-UNL-03 | R1, R2 | boundary | SO1 `invoice_id` null, flags False | `(SO1, U1, "x")` | flags False; event metadata `{"invoice_id": None}` | pass |

## `SalesManager.set_section_confirm`
Setup:
- SO1 has `contact_name "Rahim"`, line LA, all flags False, `invoice_id` null, not completed.

Call: `(order, W1, U1, section, confirmed)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-SEC-01 | R4, R9 | happy | default | `'order_info', True` | returns SO1; `order_info_confirmed True`; one event `'order_info_confirmed'`, `'Order info confirmed'`, `performed_by` U1, metadata null | pass |
| SM-SEC-02 | R5, R9 | happy | default | `'items', True` | `items_confirmed True`; event `'items_confirmed'`, `'Order items confirmed'` | pass |
| SM-SEC-03 | R9, R10 | happy | `order_info_confirmed True`; no approvers | `'order_info', False` | flag False; exactly one new event `'order_info_unconfirmed'`, `'Order info unconfirmed'`; no `approvals_reset` event | pass |
| SM-SEC-04 | R7, R9 | boundary | `items_confirmed True`; SO1 linked to `INV('draft','unpaid')` | `'items', False` | flag False; event `'items_unconfirmed'`, `'Order items unconfirmed'` | pass |
| SM-SEC-05 | R10 | side-effect | `items_confirmed True`; `AP(U1, True, 2026-09-10 10:00)`, `AP(U2, True, 2026-09-11 10:00)`, `AP(U3, False, null)` | `'items', False` | U1, U2 approved False with `approved_at` null; U3 unchanged. Events in id order: `'items_unconfirmed'`, then `'approvals_reset'` `"2 approval(s) cleared — Section unconfirmed"` `performed_by` U1. | pass |
| SM-SEC-06 | R1 | error | — | `order_id=999999999`, `'invoice', True` | `HTTPException` 400, `"Unknown section 'invoice'"` (not 404); NW | pass |
| SM-SEC-07 | R1 | boundary | default | SO1, `'Items', True` | 400 `"Unknown section 'Items'"`; NW | pass |
| SM-SEC-08 | R2 | error | — | `order_id=999999999`, `'items', True` | 404 `"Sales order with ID 999999999 not found"`; NW | pass |
| SM-SEC-09 | R2 | isolation | default | SO1 with `workspace_id=W2`, `'items', True` | 404 `f"Sales order with ID {SO1.id} not found"`; NW | pass |
| SM-SEC-10 | R3 | boundary | `order_info_confirmed True`, `contact_name` null | `'order_info', True` | returns SO1 unchanged; no error; no event | pass |
| SM-SEC-11 | R3 | boundary | `items_confirmed False`; completed; locked; `AP(U1, True)` | `'items', False` | returns SO1; no error; no event; U1 still approved | pass |
| SM-SEC-12 | R4 | error | `contact_name` null | `'order_info', True` | 400 `'Set the customer name before confirming'`; NW | pass |
| SM-SEC-13 | R4 | boundary | `contact_name ""` | `'order_info', True` | same 400; NW | pass |
| SM-SEC-14 | R4 | boundary | `contact_name "   "` | `'order_info', True` | same 400; NW | pass |
| SM-SEC-15 | R4 | boundary | `contact_name "R"` | `'order_info', True` | confirmed True | pass |
| SM-SEC-16 | R5 | error | SO1 no lines | `'items', True` | 400 `'Add at least one line item before confirming'`; NW | pass |
| SM-SEC-17 | R6 | happy | SO1 completed and locked | `'items', True` then `'order_info', True` | both succeed; flags True; two events | pass |
| SM-SEC-18 | R7 | error | `order_info_confirmed True`; locked; `AP(U1, True)` | `'order_info', False` | 400 `'Cannot unconfirm order info after invoice is confirmed'`; NW (flag True, U1 still approved) | pass |
| SM-SEC-19 | R7 | error | `items_confirmed True`; locked | `'items', False` | 400 `'Cannot unconfirm order items after invoice is confirmed'`; NW | pass |
| SM-SEC-20 | R7, R8 | error | `items_confirmed True`; locked **and** completed | `'items', False` | 400 locked message (R7 before R8); NW | pass |
| SM-SEC-21 | R8 | error | `items_confirmed True`; completed; `INV('draft','unpaid')` | `'items', False` | 400 `'Cannot unconfirm — order is complete'`; NW | pass |
| SM-SEC-22 | R11 [BUG-720] | bug | default; SQL capture on | `'items', True` | returns SO1; captured SQL locks `sales_orders` before the first INSERT into `sales_order_events` | xfail BUG-720 — fails today on: no `FOR UPDATE` on `sales_orders` |

## `SalesManager.reset_approvals`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-RA-01 | R1, R2 | happy | `AP(U1, True, 2026-09-10)`, `AP(U2, True, 2026-09-11)`, `AP(U3, False)` | `(SO1, W1, U1)` | Returns `None`. U1, U2: approved False, `approved_at` null. U3 unchanged. One event `'approvals_reset'`, `"2 approval(s) cleared — Cleared approvals"`, `performed_by` U1, metadata null. | pass |
| SM-RA-02 | R2 | boundary | `AP(U1, True)` | `(SO1, W1, None, reason="Manual")` | event `"1 approval(s) cleared — Manual"`, `performed_by` null | pass |
| SM-RA-03 | R3 | boundary | `AP(U1, False)`, `AP(U2, False)` | `(SO1, W1, U1)` | no event; rows unchanged | pass |
| SM-RA-04 | R3 | boundary | SO1 has no approvers | call | no event; no error | pass |
| SM-RA-05 | R3 | boundary | — | `order_id=999999999` | returns `None`; no error; no events anywhere | pass |
| SM-RA-06 | R1 | isolation | `AP(U1, True)` in W1; an approver row for SO1 with `workspace_id` W2, user U5, approved True | `(SO1, W1, U1)` | U1 cleared; W2 row still approved; description `"1 approval(s) cleared — Cleared approvals"` | pass |

## `SalesManager.apply_post_invoice_confirms`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-APC-01 | R1, R2, R3 | happy | SO1 all three flags False, no lines, `contact_name` null | `(SO1, W1, U1)` | Returns `None`. All three flags True. Two events in id order: `'order_info_confirmed'` `'Order info confirmed after invoice finalized'`, then `'items_confirmed'` `'Order items confirmed after invoice finalized'`, both `performed_by` U1. No other event. | pass |
| SM-APC-02 | R2, R4 | boundary | info True, items False, invoice False | call | only the `items_confirmed` event; all flags True | pass |
| SM-APC-03 | R4 | boundary | all three True | call | no events; flags True | pass |
| SM-APC-04 | R1, R3, R4 | boundary | info False, items True, invoice False | call | only the `order_info_confirmed` event; `invoice_confirmed True` | pass |

## `SalesManager.mark_order_complete`
Setup:
- SO1 has `invoice_confirmed True` and is linked to `INV('confirmed','unpaid')`.
- Lines: LA 10/10 and LS 5/5.
- `paid False`, `is_fully_delivered False`, `AP(U1, False)`.
- No returns.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-MOC-01 | R6, R8, R9 | happy | default | `(SO1, W1, U1)` | Returns SO1. `order_completed True`, `completed_at` in range (naive), `completed_by` U1. Exactly one new event: `'order_completed'` `'Order marked complete'`, `performed_by` U1. `paid` False; no `payment_status_synced` event. | pass |
| SM-MOC-02 | R7 | side-effect | invoice `payment_status 'paid'` | call | `paid True`; new events in id order: `'payment_status_synced'`, then `'order_completed'` | pass |
| SM-MOC-03 | R2 | boundary | `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2; `invoice_confirmed False`; LA 10/0; invoice paid | call | returns SO1; `completed_at`, `completed_by` unchanged; `paid` False; no event | pass |
| SM-MOC-04 | R1 | error | — | `order_id=999999999` | 404 `"Sales order with ID 999999999 not found"`; and SO1 with `workspace_id=W2` → 404 `f"Sales order with ID {SO1.id} not found"`; NW | pass |
| SM-MOC-05 | R3 | error | `invoice_confirmed False`; LA 10/9 | call | 400 `'Finalize the invoice before marking the order complete'` (R3 first); NW | pass |
| SM-MOC-06 | R4 | error | LA 10/9; `RET(SO1, 'pending')` | call | 400 `'Finish delivering and fulfilling all items before completing the order'` (R4 before R5); NW | pass |
| SM-MOC-07 | R4 | error | LS 5/4 | call | same 400 R4 message; NW | pass |
| SM-MOC-08 | R4 | boundary | LA delivered 8, refunded 2 | call | completes | pass |
| SM-MOC-09 | R4 | boundary | SO1 no lines | call | completes | pass |
| SM-MOC-10 | R5 | error | `RET(SO1, 'pending')` | call | 400 `'Complete all open returns before marking the order complete'`; NW | pass |
| SM-MOC-11 | R5 | boundary | `RET(SO1, 'completed')`, `RET(SO1, 'voided')` | call | completes | pass |
| SM-MOC-12 | R5 | isolation | SO2 (other W1 order) has `RET(SO2, 'pending')` | call on SO1 | completes | pass |
| SM-MOC-13 | R10 [BUG-720] | bug | default; SQL capture on | call | returns SO1; captured SQL locks `sales_orders` before the first UPDATE of `sales_orders` | xfail BUG-720 — fails today on: no `FOR UPDATE` on `sales_orders` |
| SM-MOC-14 | R2, RP6 (b) | boundary | SO1 `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2 (rest of the section setup); RC = `RET(SO1, 'completed')` and RA = `RET(SO1, 'pending')`; no events on SO1 | `(SO1.id, W1, U1)` | 1. returns: SO1 (`result.id == SO1.id`; no 400, because R2 runs no checks). 2. returns: `HOR(SO1) is True` ("return in progress"). 3. re-read SO1: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U2.id`, `paid is False`. 4. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. 5. nothing written: NW (rows SO1, RC, RA). | pass |
| SM-MOC-15 | R2, RP6 (c) | boundary | SO1 `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2 (rest of the section setup); RC = `RET(SO1, 'completed')` only (the last return was completed); no events on SO1 | `(SO1.id, W1, U1)` | 1. returns: SO1 (`result.id == SO1.id`). 2. returns: `HOR(SO1) is False` ("completed" again). 3. re-read SO1: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U2.id`, `paid is False`. 4. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. 5. nothing written: NW (rows SO1, RC). | pass |
| SM-MOC-16 | R2, RP6 (c), RP7 | boundary | SO1 `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2 (rest of the section setup); RC = `RET(SO1, 'completed')` and RV = `RET(SO1, 'voided')` (the last pending return was cancelled); no events on SO1 | `(SO1.id, W1, U1)` | 1. returns: SO1 (`result.id == SO1.id`). 2. returns: `HOR(SO1) is False` ("completed" again). 3. re-read SO1: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U2.id`, `paid is False`. 4. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. 5. nothing written: NW (rows SO1, RC, RV). | pass |
| SM-MOC-17 | R5, RP2 (returns of this workspace only) | isolation | Default section setup: SO1 of W1 not completed, `invoice_confirmed True`, linked to `INV('confirmed','unpaid')`, LA 10/10, LS 5/5, `AP(U1, False)`; W0 (built before W1) and W2 (built after W1); R0 = `RET(SO1, 'pending')` but with `workspace_id W0`; R2X = `RET(SO1, 'pending')` but with `workspace_id W2` (deliberately invalid cross-workspace rows, HR-16); SO1 has no return with `workspace_id W1` | `(SO1.id, W1, U1)` | 1. returns: SO1 (`result.id == SO1.id`; no 400 — another workspace's pending returns do not block). 2. re-read SO1: `order_completed is True`, `completed_by == U1.id`, `completed_at` in range (naive). 3. event: exactly 1 new `sales_order_events` row on SO1: `event_type == 'order_completed'`, `description == 'Order marked complete'`, `performed_by == U1.id`. 4. returns: `HOR(SO1) is False` (SO1's workspace is W1). 5. re-read R0: `status == 'pending'`, `workspace_id == W0.id`. 6. re-read R2X: `status == 'pending'`, `workspace_id == W2.id`. | pass |
| SM-MOC-18 | side effects "flush only" | side-effect | Default section setup: SO1 of W1 not completed, `invoice_confirmed True`, linked to `INV('confirmed','unpaid')`, LA 10/10, LS 5/5, `AP(U1, False)`, no returns; a spy wraps `session.commit` (inside a savepoint) | `(SO1.id, W1, U1)` | 1. returns: SO1 (`result.id == SO1.id`). 2. mock called: the commit spy was called 0 times. 3. re-read SO1 (before rolling back the savepoint): `order_completed is True`. Then roll back the savepoint. | pass — Author: claude |

## `SalesManager.reopen_for_return`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-ROR-01 | R1 | boundary | SO1 not completed | `(SO1, W1, U1)` | returns `False`; no event; fields unchanged | pass |
| SM-ROR-02 | R2, R2a, RP1 [BUG-2790] | bug | SO1 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2, `invoice_confirmed True`, linked to `INV('confirmed','unpaid')`; `RET(SO1, 'pending')` (the return just started); no events on SO1 | `(SO1, W1, U1)` | 1. re-read the invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`. 2. returns: `HOR(SO1) is True`. 3. returns: `False`. 4. re-read SO1: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U2.id`, `invoice_id ==` the invoice's id ("return in progress": stored completion kept and the flag true). 5. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. 6. nothing written: NW (rows SO1 and the return). | xfail BUG-2790 (strict) — fails today on: Then 3 (returns `True`; today the order is reopened) |
| SM-ROR-03 | R2, RP4 (holds today and after the fix) | side-effect | SO1 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2, `order_info_confirmed True`, `items_confirmed True`, `invoice_confirmed True`, `paid False`, linked to `INV('confirmed','unpaid')`; line LA ordered `10.00`, delivered `10.00`; `RET(SO1, 'pending')`; P1 | `(SO1, W1, U1)` | 1. returns: a `bool` (`isinstance(result, bool)`; the value itself changes with the fix). 2. re-read the invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`, `workspace_id == W1.id`. 3. re-read SO1: `invoice_id ==` the invoice's id, `invoice_confirmed is True`, `order_info_confirmed is True`, `items_confirmed is True`, `paid is False`. 4. re-read the return: `status == 'pending'`. 5. re-read LA: `quantity_delivered == 10.00`, `quantity_returned == 0.00`. 6. re-read P1: `qty == 20`. 7. count: `account_invoices` rows == the count before the call. 8. count: `product_ledger` rows == the count before the call. 9. count: `sales_deliveries` rows == the count before the call. 10. returns: `HOR(SO1) is True` (read after the call). | pass |
| SM-ROR-04 | R1 | isolation | W0 (built before W1); SO0 of W0, not completed (`order_completed False`, `completed_at` null, `completed_by` null); SO1 of W1 not completed | `(SO0, W1, U1)` (another workspace's order, caller in W1) | 1. returns: `False`. 2. re-read SO0: `order_completed is False`, `completed_at is None`, `completed_by is None`, `workspace_id == W0.id`. 3. count: `sales_order_events` rows in any workspace == 0. 4. nothing written: NW (rows SO0 and SO1). | pass |
| SM-ROR-05 | R1 | isolation | SOX of W2 (built after W1), not completed (`order_completed False`, `completed_at` null, `completed_by` null); SO1 of W1 not completed | `(SOX, W1, U1)` (another workspace's order, caller in W1) | 1. returns: `False`. 2. re-read SOX: `order_completed is False`, `completed_at is None`, `completed_by is None`, `workspace_id == W2.id`. 3. count: `sales_order_events` rows in any workspace == 0. 4. nothing written: NW (rows SOX and SO1). | pass |
| SM-ROR-06 | R2, R2a, RP1 [BUG-2790] | bug | W0 (built before W1); SO0 of W0 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U1, `invoice_confirmed True`, linked to `INV('confirmed','unpaid', ws=W0)`; no events anywhere | `(SO0, W1, U1)` (another workspace's order, caller in W1) | 1. re-read the W0 invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`. 2. returns: `False`. 3. re-read SO0: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U1.id`, `workspace_id == W0.id`. 4. count: `sales_order_events` rows in any workspace == 0. 5. nothing written: NW (row SO0). | xfail BUG-2790 (strict) — fails today on: Then 2 (returns `True`; today any completed order is reopened) |
| SM-ROR-07 | R2, R2a, RP1 [BUG-2790] | bug | SOX of W2 (built after W1) with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U5, `invoice_confirmed True`, linked to `INV('confirmed','unpaid', ws=W2)`; no events anywhere | `(SOX, W1, U1)` (another workspace's order, caller in W1) | 1. re-read the W2 invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`. 2. returns: `False`. 3. re-read SOX: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U5.id`, `workspace_id == W2.id`. 4. count: `sales_order_events` rows in any workspace == 0. 5. nothing written: NW (row SOX). | xfail BUG-2790 (strict) — fails today on: Then 2 (returns `True`; today any completed order is reopened) |
| SM-ROR-08 | R2a (holds today and after the fix) | isolation | W0 (built before W1); SO0 of W0 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U1, `invoice_confirmed True`, linked to `INV('confirmed','unpaid', ws=W0)`; SO1 of W1 with `order_completed True`, `completed_at 2026-09-02 09:00`, `completed_by` U2, linked to `INV('confirmed','unpaid')` | `(SO0, W1, U1)` | 1. returns: a `bool` (`isinstance(result, bool)`). 2. re-read the W0 invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`, `workspace_id == W0.id`. 3. re-read SO0: `invoice_id ==` the W0 invoice's id, `invoice_confirmed is True`. 4. re-read SO1: `order_completed is True`, `completed_at == 2026-09-02 09:00`, `completed_by == U2.id`. 5. re-read the W1 invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`. 6. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. | pass |
| SM-ROR-09 | R2a (holds today and after the fix) | isolation | SOX of W2 (built after W1) with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U5, `invoice_confirmed True`, linked to `INV('confirmed','unpaid', ws=W2)`; SO1 of W1 with `order_completed True`, `completed_at 2026-09-02 09:00`, `completed_by` U2, linked to `INV('confirmed','unpaid')` | `(SOX, W1, U1)` | 1. returns: a `bool` (`isinstance(result, bool)`). 2. re-read the W2 invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`, `workspace_id == W2.id`. 3. re-read SOX: `invoice_id ==` the W2 invoice's id, `invoice_confirmed is True`. 4. re-read SO1: `order_completed is True`, `completed_at == 2026-09-02 09:00`, `completed_by == U2.id`. 5. re-read the W1 invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`. 6. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. | pass |
| SM-ROR-10 | R2a, side effects "flush only" | side-effect | SO1 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2; a spy wraps `session.commit` (inside a savepoint) | `(SO1, W1, U1)` | 1. returns: a `bool` (`isinstance(result, bool)`). 2. mock called: the commit spy was called 0 times. Then roll back the savepoint. | pass — Author: claude |
| SM-ROR-11 | R2a, RP6 (a) [BUG-2790] | bug | SO1 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2, `invoice_confirmed True`, linked to `INV('confirmed','unpaid')`; RA = `RET(SO1, 'pending')` and RB = `RET(SO1, 'pending')` (two returns open at once; RB is the one just started); no events on SO1 | `(SO1, W1, U1)` | 1. returns: `HOR(SO1) is True`. 2. returns: `False`. 3. re-read SO1: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U2.id`. 4. re-read RA and RB: both `status == 'pending'`. 5. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. 6. nothing written: NW (rows SO1, RA, RB). | xfail BUG-2790 (strict) — fails today on: Then 2 (returns `True`; today the order is reopened) |
| SM-ROR-12 | R2a, RP6 (a) (holds today and after the fix) | side-effect | SO1 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2, `invoice_confirmed True`, linked to `INV('confirmed','unpaid')`; RA = `RET(SO1, 'pending')` and RB = `RET(SO1, 'pending')` | `(SO1, W1, U1)` | 1. returns: a `bool` (`isinstance(result, bool)`; the value itself changes with the fix). 2. returns: `HOR(SO1) is True` (read after the call). 3. re-read RA: `status == 'pending'`. 4. re-read RB: `status == 'pending'`. 5. re-read the invoice: `invoice_status == 'confirmed'`, `payment_status == 'unpaid'`. 6. count: `sales_order_returns` rows with `sales_order_id == SO1.id` == 2. | pass |
| SM-ROR-13 | R2a, RP6 (b) [BUG-2790] | bug | SO1 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2, `invoice_confirmed True`, linked to `INV('confirmed','unpaid')`; RC = `RET(SO1, 'completed')` and RA = `RET(SO1, 'pending')` (one return completed, another still open); no events on SO1 | `(SO1, W1, U1)` | 1. returns: `HOR(SO1) is True`. 2. returns: `False`. 3. re-read SO1: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U2.id`. 4. re-read RC: `status == 'completed'`. 5. re-read RA: `status == 'pending'`. 6. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. 7. nothing written: NW (rows SO1, RC, RA). | xfail BUG-2790 (strict) — fails today on: Then 2 (returns `True`; today the order is reopened) |
| SM-ROR-14 | R2, RP6 (c), RP7 [BUG-2790] | bug | SO1 with `order_completed True`, `completed_at 2026-09-01 08:00`, `completed_by` U2, `invoice_confirmed True`, linked to `INV('confirmed','unpaid')`; RC = `RET(SO1, 'completed')` and RV = `RET(SO1, 'voided')` (no return pending: the last one was cancelled); no events on SO1 | `(SO1, W1, U1)` | 1. returns: `HOR(SO1) is False`. 2. returns: `False`. 3. re-read SO1: `order_completed is True`, `completed_at == 2026-09-01 08:00`, `completed_by == U2.id`. 4. count: `sales_order_events` rows with `sales_order_id == SO1.id` == 0. 5. nothing written: NW (rows SO1, RC, RV). | xfail BUG-2790 (strict) — fails today on: Then 2 (returns `True`; today any completed order is reopened) |

## `SalesManager._invoice_payment_status`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-IPS-01 | R1 | boundary | `invoice_id` null | call | `None` | pass |
| SM-IPS-02 | R2 | isolation | linked to `INV('confirmed','paid', ws=W2)` | call | `None` | pass |
| SM-IPS-03 | R3 | happy | four setups, linked invoice `payment_status` `unpaid` / `partial` / `paid` / `overdue` | call each | returns the same string | pass |

## `SalesManager.sync_so_for_linked_invoice`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-SLI-01 | R1 | boundary | INV1 `('confirmed','paid')` in W1, linked to no order; SO1 paid False | `(INV1, W1, U1)` | returns `None`; no events; SO1 paid False | pass |
| SM-SLI-02 | R1 | isolation | order SOX in W2 links INV1 (W1 invoice), SOX paid False | `(INV1, W1, U1)` | no change; no event | pass |
| SM-SLI-03 | R2 | happy | SO1 links INV1 (paid); SO1 paid False | `(INV1, W1, U1)` | SO1 paid True; one `'payment_status_synced'` event | pass |
| SM-SLI-04 | R2 | boundary | SO1 and SO2 both link INV1 (paid), both paid False | call | exactly one of SO1/SO2 has paid True; exactly one `payment_status_synced` event across both | pass |

## `SalesManager.sync_so_paid`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-SP-01 | R1, R3 | happy | SO1 paid False; linked `INV('confirmed','paid')` | `(SO1, W1, U1)` | returns `True`; paid True; event `'payment_status_synced'` `'Order marked paid from linked invoice'`, metadata `{"paid": true}`, `performed_by` U1 | pass |
| SM-SP-02 | R1, R3 | happy | SO1 paid True; `INV('confirmed','partial')` | `(SO1, W1, None)` | returns `True`; paid False; description `'Order marked unpaid from linked invoice'`, metadata `{"paid": false}`, `performed_by` null | pass |
| SM-SP-03 | R1, R2 | boundary | paid False; two setups: `unpaid`, `overdue` | call each | returns `False`; no event | pass |
| SM-SP-04 | R1 | boundary | paid True; `invoice_id` null | call | returns `True`; paid False | pass |
| SM-SP-05 | R1 | isolation | paid False; linked `INV('confirmed','paid', ws=W2)` | call | returns `False`; no event | pass |
| SM-SP-06 | R1 | boundary | paid False; `INV('voided','paid')` | call | returns `True`; paid True | pass |
| SM-SP-07 | R2 | boundary | paid True; `INV('confirmed','paid')` | call | returns `False`; no event | pass |

## `SalesManager.list_approvers`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-LA-01 | R1 | error | — | `order_id=999999999`; and SO1 with W2 | 404 `"Sales order with ID 999999999 not found"` / `f"… {SO1.id} …"` | pass |
| SM-LA-02 | R2 | boundary | SO1 no approvers | `(SO1, W1)` | returns `[]` | pass |
| SM-LA-03 | R2, R3, R4 | happy | `AP(U2, assigned 2026-09-02)`, `AP(U1, assigned 2026-09-01)`, `AP(U3, assigned 2026-09-03)` | call | Returns 3 tuples in order U1, U2, U3. Each profile is that user's profile (`.id` matches). Positions: `"Sales Lead"`, `None`, `"Clerk"` (a suspended member still has a position). | pass |
| SM-LA-04 | R3 | isolation | `AP(U5)` (no W1 membership; "Boss" in W2) | call | one tuple; position `None` | pass |
| SM-LA-05 | R2 | isolation | `AP(U1)` in W1; an approver row for SO1 with `workspace_id` W2 (user U5) | call with W1 | only the U1 tuple | pass |

## `SalesManager.approval_summary`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-AS-01 | R1, R2, R3 | happy | `AP(U1, True)`, `AP(U2, False)`; `required_approvals` null | call | `(1, 2, False)` | pass |
| SM-AS-02 | R3 | boundary | both approved; null | call | `(2, 2, True)` | pass |
| SM-AS-03 | R2, R3 | boundary | both approved; `required_approvals 3` | call | `(2, 3, False)` | pass |
| SM-AS-04 | R2, R3 | boundary | U1 approved, U2 not; `required_approvals 1` | call | `(1, 1, True)` | pass |
| SM-AS-05 | R2, R3 [BUG-736] | bug | no approvers; null | call | `(0, 1, False)` | xfail BUG-736 — fails today on: returns `(0, 0, True)` |
| SM-AS-06 | R2 | boundary | no approvers; `required_approvals 2` | call | `(0, 2, False)` | pass |
| SM-AS-07 | R1 | isolation | `AP(U1, True)` in W1; approver row for SO1 in W2 (U5, approved True); null | call | `(1, 1, True)` | pass |
| SM-AS-08 | R2 | boundary | `AP(U1, True)` only; null | call | `(1, 1, True)` | pass |
| SM-AS-09 | R2 [BUG-362] | bug | schema | `SalesOrderUpdate(required_approvals=0)` | `ValidationError` on `required_approvals` | xfail BUG-362 — fails today on: no error |
| SM-AS-10 | R2 [BUG-362] | bug | schema | `SalesOrderUpdate(required_approvals=-1)` | `ValidationError` | xfail BUG-362 — fails today on: no error |
| SM-AS-11 | R2 | boundary | schema | `SalesOrderUpdate(required_approvals=1)`; `SalesOrderUpdate(required_approvals=None)` | both build | pass |

## `SalesManager.add_approver`
Setup: SO1 is not completed, `invoice_id` null, and has `AP(U1)`.

Call: `(SO1, user, W1, assigned_by=U1)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-AA-01 | R4, R5 | happy | default | U2 | Returns the approver row. Re-read: order SO1, user U2, `approved False`, `approved_at` null, `assigned_by` U1, `assigned_at` in range. One event `'approver_added'`, `"Added Bob Karim as approver"`, metadata `{"user_id": U2.id, "user_name": "Bob Karim"}`, `performed_by` U1. | pass |
| SM-AA-02 | R1 | error | — | `order_id=999999999`; and SO1 with W2 | 404 `"Sales order with ID 999999999 not found"` / `f"… {SO1.id} …"`; NW | pass |
| SM-AA-03 | R2 | error | default | U5 (not a W1 member) | 400 `"User is not an active member of this workspace"`; NW | pass |
| SM-AA-04 | R2 | boundary | default | U3 (suspended), then U4 (invited) | same 400 each; NW | pass |
| SM-AA-05 | R3 | error | default | U1 | 409 `"User is already an approver for this order"`; NW | pass |
| SM-AA-06 | R2, R3 | error | `AP(U3)` also exists | U3 | 400 member message (R2 before R3); NW | pass |
| SM-AA-07 | R3, R6 | error | SO1 completed | U1 | 409 already-approver (R3 before R6); NW | pass |
| SM-AA-08 | R6 [BUG-737] | bug | SO1 completed | U2 | 400 `"Cannot change approvers — order is complete"`; NW | xfail BUG-737 — fails today on: approver added |
| SM-AA-09 | R6 [BUG-737] | bug | SO1 locked, not completed | U2 | 400 `"Cannot change approvers — invoice is locked"`; NW | xfail BUG-737 — fails today on: approver added |
| SM-AA-10 | R6 [BUG-737] | bug | SO1 completed and locked | U2 | 400 `"Cannot change approvers — order is complete"`; NW | xfail BUG-737 — fails today on: approver added |
| SM-AA-11 | R6 | boundary | SO1 linked to `INV('draft','unpaid')`, not completed | U2 | added | pass |
| SM-AA-13 | R6 [BUG-737] | bug | SO1 locked | U2; count approvers after | only `AP(U1)` remains; no `approver_added` event | xfail BUG-737 — fails today on: 2 approvers |

## `SalesManager.remove_approver`
Setup: `AP(U1, approved True)` and `AP(U2, False)` on SO1, which is not completed and not locked.

Call: `(SO1, user, W1, performed_by=U1)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-RMA-01 | R2, R3 | happy | default | U2 | Returns `None`. The U2 row is gone and U1 remains. One event `'approver_removed'`, `"Removed Bob Karim as approver"`, metadata `{"user_id": U2.id, "user_name": "Bob Karim"}`, `performed_by` U1. | pass |
| SM-RMA-02 | R2, R3 | boundary | only `AP(U1, True)` | U1, `performed_by=None` | row gone (last approver, approved); event `performed_by` null | pass |
| SM-RMA-03 | R1 | error | default | U3 (not an approver) | 404 `"Approver not found"`; NW | pass |
| SM-RMA-04 | R1 | isolation | default | `order_id=999999999`; SO1 with `workspace_id=W2` | 404 `"Approver not found"` each; NW | pass |
| SM-RMA-05 | R1, R4 | error | SO1 completed | U3 | 404 (R1 before R4); NW | pass |
| SM-RMA-06 | R4 [BUG-737] | bug | SO1 completed | U1 | 400 `"Cannot change approvers — order is complete"`; NW (U1 row still there) | xfail BUG-737 — fails today on: row deleted |
| SM-RMA-07 | R4 [BUG-737] | bug | SO1 locked | U1 | 400 `"Cannot change approvers — invoice is locked"`; NW | xfail BUG-737 — fails today on: row deleted |
| SM-RMA-08 | R4 [BUG-737] | bug | completed and locked | U2 | 400 order-complete message; NW | xfail BUG-737 — fails today on: row deleted |

## `SalesManager.set_approval`
Setup:
- SO1 has `order_info_confirmed` and `items_confirmed` True, is not completed, and is linked to `INV('draft','unpaid')`.
- Approvers: `AP(U1, False, null)` and `AP(U2, True, 2026-03-01 10:00)`.

Call: `(SO1, user, W1, approved)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-SA-01 | R5 | happy | default | U1, `True` | returns the U1 row; approved True, `approved_at` in range; one event `'approved'` `'Approved order'`, `performed_by` U1, metadata null | pass |
| SM-SA-02 | R4, R5 | happy | default | U2, `False` | approved False, `approved_at` null; event `'approval_withdrawn'` `'Withdrew approval'`, `performed_by` U2 | pass |
| SM-SA-03 | R1 | error | default | U3, `True` | 403 `"You are not an assigned approver for this order"`; NW | pass |
| SM-SA-04 | R1 | isolation | default | U1 with `workspace_id=W2`; and `order_id=999999999` | 403 same detail each; NW | pass |
| SM-SA-05 | R2 | error | three setups: (info T, items F), (info F, items T), (F, F) | U1, `True` | 400 `'Confirm customer, order details, and items before approving'` each; NW | pass |
| SM-SA-06 | R2 | boundary | info F, items F | U2, `False` | withdraw succeeds (R2 applies to approving only) | pass |
| SM-SA-07 | R3 | happy | SO1 completed and locked | U1, `True` | approved True; event logged | pass |
| SM-SA-08 | R4 | error | SO1 completed, draft invoice | U2, `False` | 400 `'Cannot withdraw approval — order is complete'`; NW | pass |
| SM-SA-09 | R4 | error | SO1 locked, not completed | U2, `False` | 400 `'Cannot withdraw approval — invoice is locked'`; NW | pass |
| SM-SA-10 | R4 | error | completed and locked | U2, `False` | 400 order-complete message; NW | pass |
| SM-SA-11 | R6 [BUG-009] | bug | default | U2, `True` (already approved) | returns the U2 row; `approved_at == 2026-03-01 10:00`; no new event | xfail BUG-009 — fails today on: `approved_at` re-stamped and an `approved` event logged |
| SM-SA-12 | R6 [BUG-009] | bug | default | U1, `False` (not approved) | returns the U1 row; no new event | xfail BUG-009 — fails today on: `approval_withdrawn` event logged |
| SM-SA-13 | R5, R6 | boundary | default | U2 `True`; then, separately, U1 `False` | first returns the row with approved True; second returns the row with approved False and `approved_at` null (holds today and after the fix) | pass |
| SM-SA-14 | R7 [BUG-720] | bug | default; SQL capture on | U1, `True` | returns the row; captured SQL locks `sales_order_approvers` **and** `sales_orders` before the first INSERT into `sales_order_events` | xfail BUG-720 — fails today on: no `FOR UPDATE` on either table |

## `SalesManager.log_event`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-LE-01 | R1 | happy | SO1 | `(SO1, W1, "note_added", "Hello", performed_by=U1, metadata={"k": 1})` | Returns the event with an id. Re-read: `workspace_id` W1, `sales_order_id` SO1, type `note_added`, description "Hello", `performed_by` U1, metadata `{"k": 1}`, `created_at` in range. | pass |
| SM-LE-02 | R1 | boundary | SO1 | `(SO1, W1, "x", "y")` | `performed_by` null; metadata null | pass |
| SM-LE-03 | R2 | boundary | SO1 | `event_type = "a" * 50` | stored; length 50 | pass |
| SM-LE-04 | R2 | error | SO1 | `event_type = "a" * 51` | raises `sqlalchemy.exc.DBAPIError` (DataError) at flush | pass |
| SM-LE-05 | R2 | error | — | `order_id=999999999` | raises `sqlalchemy.exc.IntegrityError` | pass |
| SM-LE-06 | R2 | isolation | SO1 in W1 | `(SO1, W2, "x", "y")` | no error; stored with `workspace_id` W2 (nothing validated) | pass |

## `SalesManager.list_events`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SM-LEV-01 | R1 | error | — | `order_id=999999999`; SO1 with W2 | 404 `"Sales order with ID 999999999 not found"` / `f"… {SO1.id} …"` | pass |
| SM-LEV-02 | R2 | boundary | SO1 no events | call | `[]` | pass |
| SM-LEV-03 | R2, R3 | happy | Events on SO1 inserted in this order: E1 `created_at 2026-09-01` by U1; E2 `2026-09-03` by U2; E3 `2026-09-02`, `performed_by` null; E4 `2026-09-03` by U1 (higher id than E2). | call | Returns `[E4, E2, E3, E1]`. Profiles: U1, U2, `None`, U1. | pass |
| SM-LEV-04 | R2 | isolation | E1 on SO1 (W1); an event with `sales_order_id` SO1 and `workspace_id` W2; an event on SO2 | call `(SO1, W1)` | only E1 | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_sales_order_with_items` R1 [BUG-3219] | `SalesService.create_sales_order_from_dict` / `POST /sales-orders/` | `items: []` → `HTTPException` 400 "Sales order must have at least one item", never 500; nothing created |
| `create_sales_order_with_items` R13 [BUG-362, BUG-021] (HTTP) | `POST /sales-orders/` | Line quantity 0 / −5, price −0.01, 1.005, or 14 integer digits → 422, nothing stored |
| `create_delivery_with_items` R13 [BUG-362, BUG-021] (HTTP) | `POST /sales-deliveries/` | quantity 0 / −3 / 1.005 → 422 |
| `create_delivery_with_items` R13 [BUG-725] (HTTP) | `SalesService.create_delivery` / `POST /sales-deliveries/` | Fractional catalog quantity → 400 with the fractional-quantity message |
| `create_delivery_with_items` (all `ValueError`s) | `SalesService.create_delivery` | `ValueError` → 400 with the same message |
| `create_sales_order_with_items` R5, `create_delivery_with_items` R4 [BUG-727] | integration tests (two connections) | Two concurrent creates in one workspace both succeed with distinct numbers. The spec Overview marks this integration-only and leaves the mechanism open. |
| `create_sales_order_with_items` R2 name fallback `Item #<id>` (R2a) | `order_catalog_items` spec (`assert_unique_catalog_item_ids`) | The fallback is used when the item cannot be named. Per spec R2a, once BUG-728 is fixed R12 rejects such items before R2 runs, so this manager cannot reach it. |
| BUG-720 races (all seven methods) | integration tests (two connections) | The loser of each race waits on the row lock and gets the normal wrong-state error / no-op. The lock SQL itself is covered here: CD-19, CPD-18, CAN-09, FSI-20, SEC-22, MOC-13, SA-14 |
| `update_delivery` R3 [BUG-732] (HTTP) | `PATCH /sales-deliveries/{id}/` | `delivery_method_id: null` → 422; `tracking_number: null` clears the field |
| `approval_summary` R2 [BUG-362] (HTTP) | `PUT /sales-orders/{id}` | `required_approvals` 0 / −1 → 422 |
| `fulfill_service_item` (service pre-checks) | `SalesService.fulfill_service_item` | 404/422 versions of R1–R3 and the check that the line belongs to the order in the URL |
| `complete_delivery` (unknown delivery) | `SalesService.complete_delivery` | The service returns 404 itself for an unknown delivery |
| `reopen_for_return` R2 [BUG-2790] (caller side) | `SalesService.start_return` / `account_invoice_manager` F2 | The spec allows the fix to drop the call from `start_return` instead of changing this method. Starting a return on a completed order leaves `order_completed`, `completed_at`, `completed_by` unchanged, logs no `order_reopened` event, and the linked invoice stays frozen (edits refused per F2). Same for another workspace's order (HR-16: not found). |
| Return-in-progress RP2 / RP3 | `SalesService` (order read) / `SalesOrderResponse` | The order response carries `has_open_return: bool`, filled at read time: `True` while a return of the order is `pending`. Completed with the flag shows "return in progress"; completed without it shows "completed"; not completed shows its normal state. |
| Return-in-progress RP6 (b)/(c), RP7 (transitions) | `SalesOrderReturnManager` (complete / void return), `account_invoice_manager` `void_invoice` R3c | Completing or cancelling a return (also through its credit note) writes nothing on the order: `order_completed`, `completed_at`, `completed_by` unchanged, no `order_reopened` event. The flag drops only when the last pending return leaves `pending`. |
| `cancel_delivery` / `update_delivery` `ValueError` → 400 | `SalesService.cancel_delivery` / `update_delivery` | Translation to 400 with the same message |

## Spec gaps
None. Gaps G1–G16 and G17–G18 (from verify F2/F4) are closed by the spec's Gap log; see the Revision lines for what each one changed.

## Retired IDs
- SM-CO-11: it tested R2's `Item #<id>` fallback with two W2-item lines. After BUG-728, R12 rejects those lines first, so it would test the buggy path. Replaced by CO-50 (spec R2a).
- SM-LA-06: an approver with no profile cannot be set up, because the FK has ON DELETE CASCADE (spec Notes G8). The branch is logged as dead code.
- SM-AA-12: the `User #<id>` fallback cannot be reached, for the same reason (spec Notes G8).
- SM-RMA-09: the `User #<id>` fallback cannot be reached, for the same reason (spec Notes G8).
- SM-CD-42: it needed a stored order line with `quantity_refunded = None`. The column is NOT NULL (spec Notes G17; verify F2/F3), so the setup cannot be built. The `None` = 0 clause is covered by DLV-07.
- SM-FSI-10: same reason (spec G17). Covered by FUL-05.
- SM-RFD-07: same reason (spec G17). Covered by DLV-07 and FUL-05, which apply the same done-test.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `all_deliverable_items_delivered` | R1 | DLV-02, DLV-09 |
| | R2 | DLV-03, 04, 06, 07 |
| | R3 | DLV-05, 07, 08 |
| | R4 | DLV-01, 02 |
| `all_fulfilment_items_fulfilled` | R1 | FUL-02..06 |
| | R2 | FUL-01, 02 |
| `create_sales_order_with_items` | R1 / Errors "no lines" [BUG-3219] | CO-07, 08, 49; translation deferred |
| | R2 / Errors "duplicate" | CO-09, 10, 18; `Item #<id>` fallback deferred (R2a) |
| | R2a [BUG-728] | CO-50; fallback deferred to `order_catalog_items` |
| | R3 / Errors "min qty" | CO-12..18 |
| | R4 | CO-01, 05 |
| | R5 | CO-01, 23..28 |
| | R5 [BUG-726] | CO-29 |
| | R5 [BUG-727] | deferred (G2) |
| | R6 | CO-03 |
| | R7 | CO-04 |
| | R8 | CO-02 |
| | R9 | CO-06 |
| | R10 / Errors "invalid line data" | CO-19, 20 |
| | Errors "invalid order data" | CO-22 |
| | Inputs `factory_id` key missing | CO-51 |
| | R11 | CO-21 |
| | R12 [BUG-728] / Errors 404 | CO-30..36, 50, 52; order vs R1: CO-49 |
| | R12 [BUG-729] / Errors 400 | CO-37, 46, 53 (pass side: CO-01) |
| | R13 [BUG-362, BUG-021] / Errors 422 | CO-38 (pass), CO-39..45, 47, 48; HTTP deferred |
| | Errors "IntegrityError" | CO-29 (today), CO-32 (today) |
| `create_delivery_with_items` | R1 | CD-06 |
| | R2 | CD-07, 08, 41 |
| | R3 | CD-09 |
| | R4 | CD-01, 24 |
| | R4 [BUG-722] | CD-22, 23, 38 |
| | R4 [BUG-726] | CD-25 |
| | R4 [BUG-727] | deferred (G2) |
| | R5 | CD-10, 11 |
| | R5 [BUG-723] | CD-12, 46 |
| | R6 | CD-13, 14 |
| | R7 / Errors "over capacity" | CD-15..18, 37 (`None` refunded unreachable, G17) |
| | R7a [BUG-720] | CD-19; race deferred |
| | R8 [BUG-724] | CD-20, 21, 43 |
| | R9 | CD-01, 40 |
| | R10 | CD-10, 14, 43 |
| | R10a [BUG-723/724/725/730/362/021] | CD-44, 45, 46 (also "no delivery row" in CD-12, 20, 21, 26, 29, 30) |
| | R11 | CD-02..05, 39 |
| | R12 | CD-01 |
| | R13 (pass side) | CD-27, 28, 31, 32 |
| | R13 [BUG-362, BUG-021] | CD-33..36, 44, 45; HTTP deferred |
| | R13 [BUG-725] | CD-26 |
| | R13 [BUG-730] | CD-29, 30 |
| `complete_delivery` | R1 | CPD-14, 15 |
| | R2 [BUG-721] | CPD-16, 17 |
| | R2a [BUG-720] | CPD-18 |
| | R3 | CPD-01, 06 |
| | R3 [BUG-733] | CPD-11 |
| | R3 [BUG-734] | CPD-07..10 |
| | R4 | CPD-01, 19 |
| | R5 | CPD-02, 04, 25 |
| | R5 [BUG-735] | CPD-03 |
| | R6 | CPD-02, 28 |
| | R7 / Errors "stock" | CPD-20..25 |
| | R8 | CPD-12, 13, 26 |
| | R9 | CPD-05, 06 |
| | R9 [BUG-734] | CPD-07, 09 |
| | R10 | CPD-26 |
| | R11 | CPD-27 |
| `cancel_delivery` | R1 | CAN-04, 05 |
| | R2 | CAN-06, 07 |
| | R2a [BUG-720] | CAN-09 |
| | R3 | CAN-01, 02 |
| | R3 [BUG-733] | CAN-08 |
| | R4 | CAN-01, 03 |
| `update_delivery` | R1 | UD-12, 13 |
| | R2 | UD-14, 15 |
| | R3 | UD-01, 05, 09, 20, 21, 22 |
| | R3 [BUG-732] / Errors "null method" | UD-06, 07, 08 |
| | R3 [BUG-733] | UD-10 (xfail), UD-19 (pass) |
| | R4 | UD-01, 02, 03, 05, 18, 21 |
| | R5 | UD-04, 19, 22 |
| | R6 | UD-11, 21, 22 |
| | R7 [BUG-730] | UD-16, 17 (pass side: UD-01, 20) |
| `fulfill_service_item` | R1 | FSI-16, 17 |
| | R2 | FSI-18 |
| | R3 | FSI-19 |
| | R3a [BUG-720] | FSI-20 |
| | R4 | FSI-01, 02, 07, 13 (`None` refunded unreachable, G17) |
| | R4 [BUG-731] | FSI-09 |
| | R4/R5 [BUG-734] | FSI-11, 12 |
| | R5 | FSI-01..04 |
| | R6 | FSI-05, 06 |
| | R6 [BUG-731] | FSI-08 |
| | R7 (superseded) | covered by R4/R6 |
| | R8 | FSI-14, 15 |
| | R9 | FSI-01 |
| `_recompute_is_fully_delivered` | R1 | RFD-01, 02, 06 (`None` refunded unreachable, G17) |
| | R1 [BUG-731] | RFD-05 |
| | R2 | RFD-04 |
| | R3 | RFD-01, 03, 08 |
| `_base_sections_confirmed` | R1 | BSC-01..04 |
| `is_so_financially_locked` | R1 / R2 / R3 | LCK-01 / 02 / 03, 04, 05 (`'locked'` is a dead value, no case — G18) |
| `unlink_invoice_from_so` | R1, R2, R3 | UNL-01, 02, 03 |
| `set_section_confirm` | R1 | SEC-06, 07 |
| | R2 | SEC-08, 09 |
| | R3 | SEC-10, 11 |
| | R4 | SEC-01, 12..15 |
| | R5 | SEC-02, 16 |
| | R6 | SEC-17 |
| | R7 | SEC-04, 18, 19, 20 |
| | R8 | SEC-20, 21 |
| | R9 | SEC-01..04 |
| | R10 | SEC-03, 05 |
| | R11 [BUG-720] | SEC-22 |
| `reset_approvals` | R1 | RA-01, 06 |
| | R2 | RA-01, 02 |
| | R3 | RA-03, 04, 05 |
| `apply_post_invoice_confirms` | R1–R4 | APC-01..04 |
| `mark_order_complete` | R1 | MOC-04 |
| | R2 | MOC-03 |
| | R3 | MOC-05 |
| | R4 | MOC-06..09 |
| | R5 | MOC-06, 10, 11, 12; other workspace's returns (W0 and W2): MOC-17 |
| | Side effects "flush only" | MOC-18 |
| | R6 | MOC-01 |
| | R7 | MOC-02 |
| | R8 | MOC-01 |
| | R9 | MOC-01 |
| | R10 [BUG-720] | MOC-13 |
| | R2 × RP6 (b) / (c), RP7 (open-return states; nothing written) | MOC-14, 15, 16 |
| `reopen_for_return` | R1 | ROR-01; other workspace: ROR-04 (W0), 05 (W2) |
| | R2 [BUG-2790] | ROR-02 (xfail); other workspace: ROR-06 (W0), 07 (W2) (xfail); pass side: ROR-03, 08 (W0), 09 (W2); caller side deferred to `SalesService.start_return` |
| | R2a (state derived, nothing written; also a second return) [BUG-2790] | ROR-02, 06, 07, 11, 13 (xfail); pass side: ROR-08, 09, 10, 12 |
| Return-in-progress state | RP1 (stored completion kept) [BUG-2790] | ROR-02, 06, 07 (xfail); pass side: MOC-14..16 |
| | RP2 / RP3 (response field `has_open_return`; what the order shows) | deferred to `SalesService` / `SalesOrderResponse`; the flag's value is read with HOR in ROR-02, 03, 11..14 and MOC-14..17; workspace scope of the flag: MOC-17 |
| | RP4 (invoice stays frozen) | ROR-03 (pass), ROR-02 (xfail); F2 itself deferred to `account_invoice_manager` |
| | RP5 (completed-order guards) | existing `set_section_confirm` / `set_approval` guard cards; no new card (no guard reads the flag) |
| | RP6 (a) two open | ROR-11 (xfail), ROR-12 (pass) |
| | RP6 (b) one closed, one open | ROR-13 (xfail), MOC-14 (pass) |
| | RP6 (c) last one closed | ROR-14 (xfail), MOC-15, 16 (pass); the transitions deferred to `SalesOrderReturnManager` |
| | RP7 (cancelled through credit note) | ROR-14, MOC-16 (the `voided` state it leaves); the void itself deferred to `account_invoice_manager` `void_invoice` R3c |
| | Side effects "flush only" | ROR-10 |
| `_invoice_payment_status` | R1, R2, R3 | IPS-01, 02, 03 |
| `sync_so_for_linked_invoice` | R1 | SLI-01, 02 |
| | R2 | SLI-03, 04 |
| `sync_so_paid` | R1 | SP-01..06 |
| | R2 | SP-03, 05, 07 |
| | R3 | SP-01, 02, 04 |
| `list_approvers` | R1 | LA-01 |
| | R2 | LA-02, 03, 05 |
| | R3 | LA-03, 04 |
| | R4 | LA-03 (`None` profile unreachable, G8) |
| `approval_summary` | R1 | AS-01, 07 |
| | R2 | AS-01, 03, 04, 06, 08, 11 |
| | R2 [BUG-362] | AS-09, 10; HTTP deferred |
| | R3 | AS-01..04 |
| | R3 [BUG-736] | AS-05 |
| `add_approver` | R1 | AA-02 |
| | R2 | AA-03, 04, 06 |
| | R3 | AA-05, 07 |
| | R4 | AA-01 |
| | R5 | AA-01 (`User #<id>` fallback unreachable, G8) |
| | R6 [BUG-737] | AA-08, 09, 10, 13 (pass side: AA-07, 11) |
| `remove_approver` | R1 | RMA-03, 04, 05 |
| | R2 | RMA-01, 02 |
| | R3 | RMA-01, 02 (`User #<id>` fallback unreachable, G8) |
| | R4 [BUG-737] | RMA-06, 07, 08 (pass side: RMA-05) |
| `set_approval` | R1 | SA-03, 04 |
| | R2 | SA-05, 06 |
| | R3 | SA-07 |
| | R4 | SA-02, 08, 09, 10 |
| | R5 | SA-01, 02, 13 |
| | R6 [BUG-009] | SA-11, 12 (pass side: SA-13) |
| | R7 [BUG-720] | SA-14 |
| `log_event` | R1 | LE-01, 02 |
| | R2 / Errors | LE-03..06 |
| `list_events` | R1 | LEV-01 |
| | R2 | LEV-02, 03, 04 |
| | R3 | LEV-03 |
