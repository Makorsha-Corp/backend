# Spec — `app/managers/sales_order_return_manager.py`

> **Status:** APPROVED (2026-11-17; owner answered OQ-45, OQ-47, OQ-48, OQ-49 and confirmed BUG-2760; case-designer gaps 1–5 closed)
> **Source commit:** e48a092

> **Review round 2026-11-14 (describe, under the reviewer's delegation of 2026-11-14).** Every item that is not money or stock policy was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. The house-rule lines stand. Twin of `tests/unit/managers/purchase_order_return_manager.spec.md`: the code is the same with SO names, and every decision there is made the same way here. **Differences from the twin:** sales lines have no line number (messages name the item); a sales line always has a price (so OQ-46 does not arise); a free-text line (no catalog item) can be returned; the credit note is `payable` (we owe the customer); completion restores Product stock (OQ-49).

> **Revision 2026-11-17 (apply-review + fill-gaps).** Owner answers of 2026-11-17 applied: `validate_and_build_items` R6 → [BUG-2786], new R6a (check order); `sync_return_paid` R6 → [BUG-2788] (check in `AccountInvoiceManager.void_invoice` R3c, as the purchase twin); OQ-48 → BUG-2790 (`SalesManager.reopen_for_return` R2, rule written in `sales_manager.spec.md`); OQ-49 → BUG-2791 (`SalesService.complete_return`, no spec yet). The owner also confirmed BUG-2760. Gaps of `sales_order_return_manager.cases.md` closed (Gap log at the end): gaps 1–2 facts; gaps 3–5 decided by Claude under the reviewer's delegation (2026-11-17), gap 3 → BUG-2796, gap 5 → BUG-2797. Cards to revise: every `Q45-*`, `Q47-*` card (now bug cards), V-41 / V-42 (zero text `0`), new cards for R4a, R5 running total, R6a, R3a.

> **Revision 2026-11-17 (owner refined OQ-48).** While a return is open a completed order shows "return in progress" (invoice frozen, nothing editable) and goes back to "completed" when the return is completed or cancelled; never reopened. Applied to OQ-48 and FU-2: the state is derived from this manager's `has_open_return`, never stored (Claude, under the reviewer's delegation, 2026-11-17); rules in `sales_manager.spec.md` `reopen_for_return` R2a and *Return-in-progress state* RP1–RP7. No rule of this manager changes. Still APPROVED. Cards to revise (`sales_order_return_manager.cases.md`): the Deferred row `OQ-48 / FU-2 [BUG-2790]` (same new text as the purchase twin, sales names). `SORM-HO-*` unchanged (they already pin the flag). In `sales_manager.cases.md`: SM-ROR-02 … SM-ROR-10 (see the note under RP7 there).

> **Revision 2026-11-19 (owner in chat on the purchase twin, BUG-2810; quote fix).** Mirror checked, decided by Claude under the reviewer's delegation (2026-11-19): sales `replace` returns do **not** have the purchase problem. Planning and completing a delivery has no completed-order guard (`SalesManager.create_delivery_with_items` checks only that the invoice is finalized; `fulfill_service_item` neither, read 2026-11-19), so the replacement goes out through a normal delivery on the completed order: stock leaves at the bucket's average as for any sale, `quantity_delivered` rises again, the order stays completed and its invoice frozen (RP1, RP4). No new step, no new bug, no rule of this manager changes. FU-2 updated. The OQ-47 suggested-answer quote now reads "have already moved", matching `account_invoice_manager` `void_invoice` R3c. Still APPROVED. Cards to revise: none in `sales_order_return_manager.cases.md` (the OQ-47 cards cite R6 / R3c, whose text was already "moved"); check any card that quoted "have already come back".

> **Owner decisions applied, not asked again:** (1) invoice freeze, owner 2026-11-14 (`owner-questions.md`, "Invoice lock after completion"; BUG-2730 … BUG-2736): a completed order's invoice is frozen and corrections go through returns; a return credit note is never editable but can be voided, and the way to correct one is to void it and start a new return. (2) OQ-38 (owner 2026-11-11, BUG-2641), applied to sales the same way: delivered and refunded are separate counts; a line is done when delivered + refunded = ordered. (3) HR-15: money rounds half up.

> **Verified PASS collaborators, referenced not restated:** `tests/unit/dao/sales_order_return.spec.md` (returns and their lines), `tests/unit/dao/sales_order_item.spec.md` (`DAOSalesOrderItem.get_by_sales_order`), `tests/unit/dao/base.spec.md` (`get_by_id_and_workspace`). Order completion's open-return check is `tests/unit/managers/sales_manager.spec.md` `mark_order_complete` R5 (approved).

> **Verified by running** (my own script `v_ret.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\retprod\`, one transaction on `marker_test` with foreign-key triggers off, rolled back, nothing committed): a free-text line ("Install fee", 5 delivered) — 6 refused with `Cannot return 6 of "Install fee" — only 5 available to return`, 2 accepted with `item_id None` and the line's price; two request lines of 5 on it both accepted; the line under another order refused "does not belong to this sales order". Everything else was verified on the purchase twin with identical code (same model property arithmetic, same branches): see that spec's "Verified by running". **Read, not run:** `SalesService.start_return`, `_attach_return_invoice_for_so`, `complete_return`, `void_return`, `list_returns`, `get_return`; `SalesManager.reopen_for_return`, `mark_order_complete`; `InvoicePaymentManager._sync_linked_order`; the models `SalesOrderItem`, `SalesOrderReturn`, `SalesOrderReturnItem`; the schema `app/schemas/sales_order_return.py`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs.

## Review
> All items decided (delegation) or parked as owner questions; nothing blocks the test designer.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| OQ-45 | A return's price per unit can be anything the user types: negative, zero, or above the selling price | bug — between 0 and the order line's price (BUG-2786) | owner, 2026-11-17 |
| OQ-47 | Voiding a return's credit note from the invoice page leaves the return as it was | bug — pending return cancelled with it; completed → void refused (BUG-2788) | owner, 2026-11-17 |
| OQ-48 | Starting a return reopens a completed order, which lifts its invoice freeze | bug — a return never reopens the order; while a return is open the completed order shows "return in progress" (derived `has_open_return`), invoice frozen, nothing editable; back to "completed" when the return closes (BUG-2790, rules in `sales_manager.spec.md`) | owner, 2026-11-17; refined by the owner 2026-11-17 |
| OQ-49 | A catalog line fulfilled without delivery (no stock taken at sale) still adds stock back when returned | bug — restock only lines that took stock out (BUG-2791, sales service) | owner, 2026-11-17 |
| Q1 | After a return is completed, its quantity is taken off twice from what can still be returned | bug — counted once (BUG-2760) | Claude, delegated; confirmed by owner 2026-11-17 |
| Q2 | The same order line sent twice in one return is checked line by line, so more than was delivered can be returned | bug — the repeats are added up (BUG-2761) | Claude, delegated |
| P1 | Return quantities and prices with more than 2 decimals are accepted | bug — refused, 422 (BUG-2762) | Claude, delegated (BUG-604 precedent) |
| G3 | Another workspace's pending return lines reserve quantity on this workspace's line | bug — ignored, HR-16 (BUG-2796) | Claude, delegated (2026-11-17) |
| G5 | The message shows the name of a catalog item of another workspace | bug — HR-16, the line's own description or id (BUG-2797) | Claude, delegated (2026-11-17) |
| D1 | The "too many" message names the item, not a line number | intended | Claude, delegated |

Decided by house rules: no lock while checking quantities (BUG-2763), no lock on the return read before complete / void (BUG-2764), a return's `items` in no fixed order (BUG-2765).

### House-rule violations — applied automatically

- **HR-10** `validate_and_build_items` R9 — the order's lines and their pending reservations are read with no row lock, then the caller creates the return. Two returns started at the same moment on one line both see the same quantity available and both are accepted (stock and credit notes = real harm). Intended: the order's lines are read `FOR UPDATE` (or the order row is locked first), so the second start waits and gets the normal "only N available" error.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2763 (pattern `hr-10-unlocked-state-transition`). Rules: `validate_and_build_items` R9.
- **HR-10** `get_return` R4 — `complete_return` and `void_return` read the return through `get_return`, check `status == 'pending'`, then restore Product stock and lower delivered (complete) or void the credit note (void), with no row lock. Two completes at once both add the stock back; a complete and a void at once leave a completed return with a voided credit note. Intended: `get_return` gains `for_update: bool = False`; with `True` the return row is read `SELECT … FOR UPDATE`; `complete_return` and `void_return` pass `True`, so the loser sees the new status and gets "Only a pending return can be completed" / "… cancelled".
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2764 (pattern `hr-10-unlocked-state-transition`; the purchase twin's BUG-2754, and BUG-800 for the purchase stock side). Rules: `get_return` R4.
- **HR-6** `get_return` R5, `list_returns` R2 — a return's lines come back through `SalesOrderReturn.items`, which has no `order_by`; the response lists them in database order. Same as BUG-2425 for the DAO's `get_by_return` (DAO spec FU-1 (a)). Intended: `id` ascending, via `order_by=SalesOrderReturnItem.id` on the relationship.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2765 (pattern `unordered-pagination`). Rules: `get_return` R5, `list_returns` R2.

Checked and **not** a new line here: the same list as the purchase twin (**HR-4, HR-5, HR-7, HR-8, HR-9, HR-15, HR-16, HR-1/2**), with the same reasons. **HR-16** here: a line of this order id under another workspace is "does not belong" (R2); a return of another workspace or order is 404; a credit-note id pointing into another workspace counts as none.

### Owner questions — answered by the owner (2026-11-17), recorded in `docs/testing/owner-questions.md`

### OQ-45. A return's price per unit can be anything the user types — 🐞 BUG-2786
**Background:** Starting a sales return immediately creates and confirms a credit-note invoice of type `payable` (we owe the customer). Each credit-note line is quantity × the return line's unit price. The request may send a `unit_price` per line; if not, the order line's selling price is used. Nothing checks the value sent. Same question as the purchase twin; one answer covers both.
**What happens today:** The price sent is used as is: negative, `0`, or above the selling price (verified on the twin's identical code: `-5`, `0`, `99999`).
**Example:** SO-2026-021 sold 4 chairs at 2,500.00. The customer returns 1; the user types 25,000.00 by mistake: the confirmed credit note says we owe the customer 25,000.00, and it cannot be edited (only voided). A price of −100.00 makes the customer owe us for goods they gave back.
**Rules affected:** `validate_and_build_items` R6 (tagged), R6a
**Suggested answer:** bug — a return price must be ≥ 0 and ≤ the order line's price (default: the order line's price); otherwise 400 `Return price for "{item}" must be between 0 and {line price}`, nothing created.
**Alternatives:** (a) intended — any agreed credit. (b) only refuse negative prices.
**Answer:** owner, 2026-11-17: suggested answer → BUG-2786
**Resolution:** 🐞 BUG-2786 (pattern `unbounded-credit-amount`, as the purchase twin's BUG-2785). Below 0 or above the line's stored price → 400 `Return price for "{item name}" must be between 0 and {line price}`, nothing created; 0 and exactly the line price accepted. Rules: `validate_and_build_items` R6 (tagged), R6a.

### OQ-47. Voiding a return's credit note from the invoice page leaves the return as it was — 🐞 BUG-2788
**Background:** As the purchase twin. "Cancel return" (`void_return`) voids the credit note and marks the return `voided`. Voiding the credit note from the invoice page voids only the invoice; the return is never told. The owner's 2026-11-14 rule "void it and start a new return" works only while the return is pending.
**What happens today:** A pending return with a voided credit note stays `pending` and can still be completed (stock comes back, nothing is owed to the customer); a completed one stays `completed`.
**Example:** Return SR-2026-003 takes back 2 tables (credit 9,000.00). Its credit note is voided from the invoice page to correct the amount. The return is then completed: the tables go back into stock and the customer is owed nothing; a new return for them is refused ("only 0 available to return").
**Rules affected:** `sync_return_paid` R6 (tagged); `account_invoice_manager` `void_invoice` R3c
**Suggested answer:** bug — voiding the credit note of a pending return cancels the return too (→ `voided`, quantity freed); voiding the credit note of a completed return is refused (400 `This return is completed — its goods have already moved. Start a new return or issue a separate credit note.`).
**Alternatives:** (a) intended — kept apart. (b) only "Cancel return" may void a return credit note.
**Answer:** owner, 2026-11-17: suggested answer → BUG-2788
**Resolution:** 🐞 BUG-2788 (one bug for both return kinds; pattern `linked-record-not-updated`). The check lives in `AccountInvoiceManager.void_invoice` R3c (decided by Claude under the reviewer's delegation, 2026-11-17, consistent with its O1 placement: every void path goes through it). Rules: `sync_return_paid` R6 (tagged).

### OQ-48. Starting a return reopens a completed order, which lifts its invoice freeze — 🐞 BUG-2790
**Background:** Under the owner's freeze a completed order's invoice cannot be reverted, voided or deleted. Starting a return on a completed sales order clears `order_completed`, `completed_at`, `completed_by` (`SalesManager.reopen_for_return`). While the return is pending (and after a `replace` return, until redelivered) the order is not completed, so its invoice is not frozen.
**What happens today:** The order's own invoice can be voided (cancelling its payments) or reverted and edited again once any return is started.
**Example:** SO-2026-018 is completed, invoice 12,000.00 frozen. One chair comes back; the user starts a return; the 12,000.00 invoice can now be voided from the invoice page.
**Rules affected:** none here — `SalesManager.reopen_for_return`, `AccountInvoiceManager` F2 (FU-2).
**Suggested answer:** bug — once an order has been completed, its invoice stays frozen for good, even while a return reopens the order.
**Alternatives:** (a) a return does not reopen the order. (b) intended.
**Answer:** owner, 2026-11-17: a return never reopens a completed order or lifts its invoice freeze → BUG-2790. **Refined by the owner 2026-11-17:** while a return is open a completed order shows "return in progress"; the invoice stays frozen and nothing on the order is editable; when the return is completed or cancelled the order goes back to "completed". Never reopened to open/editable.
**Resolution:** 🐞 BUG-2790 (pattern `completed-order-invoice-not-frozen`). Rule: `sales_manager.spec.md` `reopen_for_return` R2 (tagged, 2026-11-17), R2a and `sales_manager.spec.md` *Return-in-progress state* RP1–RP7 (refinement, 2026-11-17). The "return in progress" state is derived from this manager's `has_open_return` (R1–R3), never stored: `order_completed` stays `True`, so freeze F2 keeps the invoice frozen and the completed-order guards keep the order uneditable. Shape chosen by Claude under the reviewer's delegation (2026-11-17). Two returns at once, one closing while another stays open, and a return cancelled through its credit note (BUG-2788): RP6–RP7. No rule of this manager changes.

### OQ-49. A catalog line fulfilled without delivery still adds stock back when returned — 🐞 BUG-2791
**Background:** A sales line either needs delivery (`requires_delivery = true`: stock leaves when the delivery is completed) or is fulfilled directly (`false`: one click, "no stock movement"). Completing a return adds the returned quantity back to Product stock for **every** line with a catalog item (`SalesService.complete_return` → `ProductManager.apply_sale_return`), without looking at `requires_delivery`. Free-text lines add nothing.
**What happens today:** Returning a directly fulfilled catalog line adds stock that never left.
**Example:** SO-2026-030 has "Desk lamp × 3", fulfilled directly: 3 lamps leave the shop but Product stock stays at 20. The customer brings 1 lamp back; completing the return makes stock 21, while 18 lamps are really on the shelf.
**Rules affected:** none here — `SalesService.complete_return` (FU-1 (a)); `ProductManager.apply_sale_return` adds whatever it is given.
**Suggested answer:** bug — a return adds stock back only for lines that took stock out (`requires_delivery = true`); a directly fulfilled line's return moves money (credit note) and quantities only.
**Alternatives:** (a) intended — returned goods are physically here now, so they are added (and direct fulfilment should start taking stock out instead). (b) ask the user at completion whether the goods go back to stock.
**Answer:** owner, 2026-11-17: suggested answer (restock only lines that actually took stock out) → BUG-2791
**Resolution:** 🐞 BUG-2791 (pattern `stock-move-ignores-fulfilment-mode`). `SalesService.complete_return` calls `ProductManager.apply_sale_return` only for return lines whose sales line has a catalog item **and** `requires_delivery = true`; other lines change quantities and money only. Rule belongs to the sales service spec (FU-1 (a)); no rule of this manager changes.

### Decided under the reviewer's delegation (2026-11-14)

### Q1. A completed return's quantity is taken off twice from what can still be returned — 🐞 BUG-2760
**Background:** Each sales line keeps `quantity_delivered` and `quantity_returned`. Completing a return lowers `quantity_delivered` ("the goods physically came back") **and** raises `quantity_returned`. What can still be returned = delivered − returned − pending.
**What happens today:** A completed return counts twice (same arithmetic as the purchase twin, verified there: 10 → return 4 completed → 2.00 available instead of 6).
**Example:** 10 chairs delivered, 4 returned (completed). Later 3 more come back: the user is told "only 2.00 available to return".
**Rules affected:** `validate_and_build_items` R4
**Answer:** bug — what can be returned = delivered (already net of completed returns) − quantity in pending returns, never below 0 (decided by Claude under the reviewer's delegation, 2026-11-14, as the twin's BUG-2750)
**Confirmed:** owner, 2026-11-17: returnable counted once.
**Resolution:** 🐞 BUG-2760 (pattern `returned-quantity-counted-twice`). Fix in `SalesOrderItem.quantity_available_to_return`. Rules: `validate_and_build_items` R4 (tagged).

### Q2. The same order line sent twice in one return is checked line by line — 🐞 BUG-2761
**Background:** As the twin.
**What happens today:** Verified: two request lines of 5 on a line with 5 delivered were both accepted.
**Example:** "Install fee × 5" added twice: the customer is credited for 10 installs of 5 sold.
**Rules affected:** `validate_and_build_items` R5
**Answer:** bug — repeats are added up and the total checked; over → 400 with the total (`Cannot return 10 of "Install fee" — only 5.00 available to return`) (decided by Claude under the reviewer's delegation, 2026-11-14, as BUG-2751)
**Resolution:** 🐞 BUG-2761 (pattern `repeated-line-bypasses-limit`). Rules: `validate_and_build_items` R5 (tagged).

### P1. Return quantities and prices with more than 2 decimals are accepted — 🐞 BUG-2762
**Background / today / example:** as the twin's P1 (`Numeric(15,2)` columns, schema checks only > 0; `0.004` stored `0.00`).
**Rules affected:** `validate_and_build_items` R10 (schema)
**Answer:** bug — per BUG-604 precedent: `SalesOrderReturnItemCreate` refuses more than 2 decimal places or more than 13 integer digits in `quantity_returned` / `unit_price` (422) (decided by Claude under the reviewer's delegation, 2026-11-14)
**Resolution:** 🐞 BUG-2762 (pattern `unbounded-decimal-input`). Fix in `app/schemas/sales_order_return.py`. Rules: `validate_and_build_items` R10 (tagged).

### D1. The "too many" message names the item — ✅ intended
**What happens today:** `Cannot return 6 of "Install fee" — only 5.00 available to return` (stored values; in-session `5` prints as `5`): sales lines have no line number; the name is the catalog item's, or the free-text description.
**Example:** The user sees the same name as on the order page.
**Rules affected:** `validate_and_build_items` R3
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-14)
**Resolution:** no bug. Rules: `validate_and_build_items` R3 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Sales service** (`start_return`, `_attach_return_invoice_for_so`, `complete_return`, `void_return`; no spec yet) | (a) OQ-49: `complete_return` restores Product stock for every catalog line, whatever `requires_delivery`; rule there → BUG-2791 (owner 2026-11-17). (b) `start_return` refuses an order with nothing delivered / fulfilled, then calls `validate_and_build_items`; a completed order is allowed (owner freeze). (c) Credit-note lines use the in-session `unit_price × quantity`; must be rounded half up (HR-15). (d) `complete_return` / `void_return` pass `for_update=True` to `get_return` (BUG-2764). (e) `void_return` sets no `updated_by`. | reading the callers |
| FU-2 | **Sales manager** (`reopen_for_return`) | OQ-48 answered → BUG-2790; rule `reopen_for_return` R2 rewritten in `sales_manager.spec.md` (2026-11-17). A `replace` return then leaves a delivery gap on a completed order: redelivering on a completed order must stay possible (sales service). **2026-11-17 (OQ-48 refined):** the return-in-progress state is decided (`sales_manager.spec.md` *Return-in-progress state* RP1–RP7); how the replacement is redelivered while the order stays completed and uneditable is still open (order workflow, owner). **2026-11-19 (mirror of BUG-2810):** closed without a new step — a normal delivery on the completed order carries the replacement (no completed-order guard on delivery planning or completion; stock out at the bucket average; order stays completed, invoice frozen). For the **sales service** spec: keep delivery planning and fulfilment allowed on a completed order while its lines have a gap (ordered − delivered − refunded > 0); do not add a completed-order guard there. | reading `start_return`; 2026-11-19 |
| FU-3 | **Account invoice manager** (`void_invoice`) | OQ-47 answered → BUG-2788; rule `void_invoice` R3c (2026-11-17). | `sync_return_paid` |

## Overview
`SalesOrderReturnManager` holds the checks and reads for **sales order returns** (delivered or fulfilled goods taken back from the customer, lifecycle `pending` → `completed` | `voided`). It checks a new return's lines against what can still be returned and builds the rows to store, looks returns up for one order, tells the order whether a return is still open, and keeps the return's `paid` flag in step with its credit-note invoice (`payable`). It writes nothing except `paid`. Callers: `SalesService` (`start_return`, `complete_return`, `void_return`, `list_returns`, `get_return`), `SalesManager.mark_order_complete` (`has_open_return`), `InvoicePaymentManager._sync_linked_order` (`sync_return_paid`). It never commits and, today, takes no lock.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none.
**Integration-only behavior:** none.

**Notes for the test designer:**
- Rows needed: `sales_orders`, `sales_order_items` (a line needs `item_id` **or** `description` — check constraint; `unit_price` and `line_total` NOT NULL), returns and lines (parents per `tests/unit/dao/sales_order_return.spec.md` Notes), and an `account_invoices` row for `sync_return_paid`.
- "Available to return" reads `SalesOrderItem.return_items` and each return's status; `session.expire_all()` after inserting returns directly.
- "A completed return" = what `complete_return` does: return `status = 'completed'`; `quantity_delivered -= q`, `quantity_returned += q`, `refund` also `quantity_refunded += q`.
- Concurrency rules (`validate_and_build_items` R9, `get_return` R4) need two transactions; no unit case.

## Not specified
- `SalesOrderReturnManager.__init__` — wires the DAOs; no logic.
- `sales_order_return_manager` — module singleton.
- Inherited `BaseManager` methods — `tests/unit/managers/base_manager.spec.md`; unused on this manager.

---

## `SalesOrderReturnManager.has_open_return(session, sales_order_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `SalesManager.mark_order_complete` R5)

**Purpose:** Does this order still have a return in progress?

**Inputs:** `sales_order_id`, `workspace_id` — ints, not checked to exist.

**Returns:** `bool`.

**Rules:**
- **R1.** `True` when the order has at least one return of this workspace with status `pending`; `False` when all its returns are `completed` / `voided`, when it has none, or for an unknown order. Statuses per `DAOSalesOrderReturn.get_open_by_sales_order` R1.
- **R2.** A pending return of the same order id under another workspace does not count.
- **R3.** Nothing is written.

**Errors:** none. **Side effects:** none.

---

## `SalesOrderReturnManager.validate_and_build_items(session, *, sales_order_id, workspace_id, data)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `SalesService.start_return`)

**Purpose:** Check each requested return line against the order and against what can still be returned, and build the return-line rows.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `sales_order_id` | int | Not checked to exist (the service reads the order first). |
| `workspace_id` | int | Only lines of this workspace are considered. |
| `data` | `SalesOrderReturnCreate` | Fields (G2, from the schema): `return_type` **required** `Literal['replace', 'refund']`; `items` **required** list; `reason`, `notes` optional `str \| None`, default `None`. Line: `so_item_id`, `quantity_returned` **required**; `unit_price`, `notes` optional (default `None`). Extras ignored. Schema before the manager: `return_type` `replace` / `refund` (else 422); `items` not empty (`At least one item must be selected for return`); every `quantity_returned` > 0 (`All return quantities must be positive`). Per line: `so_item_id` int, `quantity_returned` Decimal, `unit_price` Decimal or `None`, `notes` str or `None`. |

**Returns:** `list[dict]`, one per request line, in request order: `{'so_item_id', 'item_id', 'quantity_returned', 'unit_price', 'notes'}`. Nothing is stored.

**Rules:**
- **R1.** Request lines are checked in request order; the first failure raises and nothing is returned. A request that passes returns one dict per request line, in request order.
- **R2.** `so_item_id` not a line of this order in this workspace → 400 `Item {so_item_id} does not belong to this sales order` (unknown id, line of another order — verified, line of this order id under another workspace; HR-16). Lines are `DAOSalesOrderItem.get_by_sales_order` R1–R2.
- **R3.** ✅ A quantity above what can be returned (R4) → 400 `Cannot return {quantity as sent} of "{item name}" — only {available} available to return`; `{available}` prints `0` when nothing is left, at exactly zero or below (G1, `max(Decimal(0), …)`; the twin verified `only 0 available to return`). The name is the catalog item's name, or the line's description for a free-text line (verified "Install fee"). Exactly the available quantity is accepted.
- **R4.** [BUG-2760] What can be returned on a line = `quantity_delivered` − (sum of `quantity_returned` of this line's return lines whose return is `pending`), never below 0. Delivered is already lowered by completed returns; voided returns reserve nothing; refunded quantity does not count (OQ-38). Lines fulfilled directly count the same way (their `quantity_delivered` is the fulfilled quantity). *(Today: completed returns are taken off again through `quantity_returned` — the twin's verified 10 → 4 completed → 2.00 available instead of 6.)*
- **R3a.** [BUG-2797] (HR-16, decided by Claude under the reviewer's delegation, 2026-11-17) The name is the catalog item's only when that item is of this workspace; otherwise (invalid data) the line's description, or `Item {so_item_id}` (the id the caller sent) when it has none. A removed (inactive or soft-deleted) item of this workspace still gives its name: it is the order's history. *(Today: the item is read through the relationship whatever its workspace; verified `Cannot return 3 of "OtherWsName" …` for an item of another workspace.)*
- **R4a.** [BUG-2796] (HR-16, decided by Claude under the reviewer's delegation, 2026-11-17) Only return lines of this workspace on returns of this workspace reserve quantity; another workspace's pending return line pointing at this line is ignored. *(Today: it reserves, as verified on the purchase twin.)*
- **R5.** [BUG-2761] Request lines naming the same order line are added up and the total checked as in R3, with the total in the message; when it fits every request line is kept. The total is a running total in request order: the error is raised at the repeat that goes over and names that running total; an earlier failing line wins (R1) (G4, decided by Claude under the reviewer's delegation, 2026-11-17, as the twin). *(Today: each checked alone; 5 + 5 on 5 delivered both accepted, verified.)*
- **R6.** [BUG-2786] (owner, OQ-45) A sent `unit_price` must be ≥ 0 and ≤ the order line's stored price; otherwise 400 `Return price for "{item name}" must be between 0 and {line price}` (name per R3 / R3a, price as stored, e.g. `3.00`), nothing returned. Within the range it is used as sent; `0` and exactly the line price are accepted. *(Today: any value kept as sent.)*
- **R6a.** Check order per request line (decided by Claude under the reviewer's delegation, 2026-11-17): lines in request order; for each, R2, then R3 / R5, then R6. The first failure raises.
- **R7.** When no `unit_price` is sent, the order line's `unit_price` is used (always set: NOT NULL on sales lines; verified `3.00`).
- **R8.** Each dict has `so_item_id` = the line's id, `item_id` = its catalog item or `None` for a free-text line (verified), `quantity_returned` and `notes` as sent.
- **R9.** [BUG-2763] (HR-10) The order's lines are read with a row lock (`FOR UPDATE`) before the check, so two concurrent starts cannot together reserve more than is available. *(Today: no lock.)* Not unit-testable; no case.
- **R10.** [BUG-2762] (schema) More than 2 decimal places or more than 13 digits before the point in `quantity_returned` or `unit_price` is refused by `SalesOrderReturnItemCreate` (422). *(Today: accepted; `0.004` is stored `0.00`, as verified on the twin.)*
- **R11.** Nothing is written; order lines unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| line not on this order / workspace | `HTTPException` 400 | `Item {so_item_id} does not belong to this sales order` |
| more than can be returned | `HTTPException` 400 | `Cannot return {qty} of "{item name}" — only {available} available to return` |
| price below 0 or above the line price (BUG-2786) | `HTTPException` 400 | `Return price for "{item name}" must be between 0 and {line price}` |
| schema failures (incl. BUG-2762) | `pydantic.ValidationError` (422) | as the purchase twin |

**Side effects:** none.

---

## `SalesOrderReturnManager.get_return(session, return_id, sales_order_id, workspace_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `SalesService.complete_return`, `void_return`, `get_return`)

**Purpose:** One return of one order, or 404.

**Inputs:** `return_id`, `sales_order_id`, `workspace_id` — ints. (After BUG-2764: `for_update: bool = False`.)

**Returns:** the `SalesOrderReturn`, any status.

**Rules:**
- **R1.** A return of this workspace belonging to this order is returned, any status.
- **R2.** Unknown id, another order's return, another workspace's return → 404 `Return with ID {return_id} not found`.
- **R3.** Nothing is written.
- **R4.** [BUG-2764] (HR-10) With `for_update=True` the return row is read `SELECT … FOR UPDATE`; `complete_return` and `void_return` use it. Default unlocked. *(Today: no parameter, no lock.)* Concurrency not unit-testable.
- **R5.** [BUG-2765] (HR-6) The return's `items` come in `id` ascending. *(Today: no `order_by` on the relationship.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other order / other workspace | `HTTPException` 404 | `Return with ID {return_id} not found` |

**Side effects:** none.

---

## `SalesOrderReturnManager.list_returns(session, sales_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `SalesService.list_returns` → `GET /sales-orders/{id}/returns/`)

**Purpose:** Every return of one order.

**Returns:** `list[SalesOrderReturn]`, possibly empty.

**Rules:**
- **R1.** Exactly `DAOSalesOrderReturn.get_by_sales_order` R1–R3: every status, newest first, ties by `id` descending after BUG-2423; unknown order / other workspace → `[]`.
- **R2.** [BUG-2765] (HR-6) Each return's `items` in `id` ascending.

**Errors:** none. **Side effects:** none.

---

## `SalesOrderReturnManager.sync_return_paid(session, ret, workspace_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `InvoicePaymentManager._sync_linked_order`; `SalesService.void_return`)

**Purpose:** Keep `paid` equal to "its credit note is fully paid" (here: we have paid the customer back in full).

**Returns:** `bool` — `True` when `paid` changed.

**Rules:**
- **R1.** New value `True` only when `invoice_id` is set, that invoice is in this workspace, and its `payment_status` is exactly `'paid'`.
- **R2.** `'unpaid'`, `'partial'`, `'overdue'` → `False`; a voided credit note (reset to `'unpaid'` by the void) → `False`.
- **R3.** No credit note (`NULL`), or an id that is not an invoice of this workspace (HR-16) → `False`.
- **R4.** Already equal → `False`, nothing written or flushed.
- **R5.** Different → `paid` set, flushed, `True`; `updated_at` by `onupdate`; `updated_by`, `status`, `completed_*` untouched; not committed.
- **R6.** [BUG-2788] (owner, OQ-47) Voiding a return's credit note, from any path, keeps the return in step: a `pending` return becomes `voided` (quantity freed, `paid` re-synced to `False`); for a `completed` return the void is refused (400, nothing changed). Done by `AccountInvoiceManager.void_invoice` R3c, not by this method, which still only writes `paid`. *(Today: the status never follows the credit note.)*

**Errors:** none.

**Side effects:** at most `sales_order_returns.paid` (+ `updated_at`), flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 27 | any pending return / none | `has_open_return` R1, R2 |
| 41–45 | order lines of this order and workspace (map) | `validate_and_build_items` R2 |
| 47 | loop over request lines | `validate_and_build_items` R1 |
| 49 | line not in the map | `validate_and_build_items` R2 |
| 54 | available = delivered − returned − pending (model property, `max(0, …)`) | `validate_and_build_items` R4 |
| 55 | requested > available / equal | `validate_and_build_items` R3, R5 |
| 59 | item name: catalog name, else description | `validate_and_build_items` R3 |
| 63 | `unit_price is not None` → sent / order line's | `validate_and_build_items` R6, R7 |
| 64–70 | dict built (`item_id` may be `None`) | `validate_and_build_items` R8 |
| 76–77 | not found, or another order | `get_return` R1, R2 |
| 93 | `invoice_id is None` | `sync_return_paid` R3 |
| 94–97 | invoice in workspace and `'paid'` | `sync_return_paid` R1–R3 |
| 98 | unchanged → `False` | `sync_return_paid` R4 |
| 100–102 | changed → set, flush, `True` | `sync_return_paid` R5 |
| schema `validate_return` | empty items / quantity ≤ 0 | `validate_and_build_items` Inputs, Errors |

## Gap log
- G1 (sales_order_return_manager.cases.md gap 1) — Fact — R3: `available` prints `0` at exactly zero and below (`max(Decimal(0), …)` returns its first argument on a tie; verified on the twin 2026-11-17). OQ-47 example corrected to `only 0 available to return`.
- G2 (gap 2) — Fact — Inputs: `SalesOrderReturnCreate` requires `return_type`, `items`; `reason`, `notes` optional `str | None`; line `so_item_id`, `quantity_returned` required, `unit_price`, `notes` optional; extras ignored (verified from `model_fields`).
- G3 (gap 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-17), HR-16 — new R4a: another workspace's pending return lines do not reserve → BUG-2796.
- G4 (gap 4) — Intent, decided by Claude under the reviewer's delegation (2026-11-17) — R5 running total, first failing line in request order wins; R6a check order.
- G5 (gap 5) — Fact + intent — the name comes from the item relationship whatever the item's workspace or state (verified: an item of another workspace shows its name; a removed item cannot vanish, FK `RESTRICT`). Decided by Claude under the reviewer's delegation (2026-11-17), HR-16: new R3a → BUG-2797; a removed item of this workspace keeps its name.
