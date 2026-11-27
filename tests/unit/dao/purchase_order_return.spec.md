# Spec — `app/dao/purchase_order_return.py`

> **Status:** APPROVED (2026-11-10; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-09 (describe).** No owner answer was needed. **Delegated:** P1–P3 accepted from precedent and D1 decided, by Claude under the reviewer's delegation (2026-11-09). None of them is the owner's own answer. The house-rule lines stand. Twin of `tests/unit/dao/sales_order_return.spec.md`: the two DAOs are the same code with `PR`/`SR`, and every decision here is made the same way there.

> **Review round 2026-11-10 (fill-gaps).** No owner question for this DAO. **Delegated (2026-11-10), decided by Claude under the reviewer's delegation, none of them the owner's own answer:** `get_by_invoice_id(None)` (new R4), number-prefix case (new `generate_return_number` R1a), and what `create_with_user` does with a taken next number once BUG-2427 is fixed (R3a). Gaps of `purchase_order_return.cases.md` closed (Gap log at the end).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated. Both classes inherit every `BaseDAO` method unchanged; the callers use the inherited `get_by_id_and_workspace` (the return, in `PurchaseOrderReturnManager.get_return`) and `create` (each return line, in `PurchaseOrderService.start_return`).
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** (throwaway scripts `schema.py`, `v_ret.py` with my own harness `hb.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omd\B\`, each transaction rolled back against `marker_test`, foreign-key triggers off inside the transaction (`SET LOCAL session_replication_role = replica`) so no purchase order, invoice or item rows were needed; nothing committed): the columns, defaults, constraints and indexes of both tables; numbering in an empty workspace, the second return, another workspace's next number, years `1` and `2099`, a hand-made `PR-<year>-XYZ` row counted; workspace B's first return colliding with workspace A's `PR-2026-001` (23505); the year taken from a patched `datetime.now()` (2031 → `PR-2031-001`); `user_id=None` (23502); `return_type="banana"` stored; `reason=""` stored as `""`; two counts before an insert; 999 returns then the next number; the order of `get_by_purchase_order` with four returns of one `created_at` under a forced sequential scan, before and after an update (`22581, 22582, 22585, 22587` → `22582, 22585, 22587, 22581`); `get_open_by_purchase_order` with a `completed`-free mix and a hand-set `'Pending'`; `get_by_invoice_id` with two returns on one invoice, another workspace, an unknown invoice; `get_by_return` order of three lines before and after an update (`22081, 22082, 22080`), a line of another workspace on the return, an unknown return. **Read, not run:** `app/managers/purchase_order_return_manager.py`, `app/services/purchase_order_service.py` (`_attach_return_invoice_for_po`, `start_return`, `complete_return`, `void_return`, `list_returns`, `get_return`), `app/managers/purchase_order_manager.py` (`mark_order_complete` open-return check, `delete_purchase_order`), `app/managers/invoice_payment_manager.py` (`_sync_linked_order`), the endpoints in `app/api/v1/endpoints/purchase_orders.py`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs.

## Review
> All answered; applied 2026-11-09.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A workspace cannot start its first return of the year while another workspace already has that number | bug — numbers unique per workspace (BUG-2426) | Claude, delegated (BUG-726 precedent) |
| P2 | Two returns started at the same moment in one workspace get the same number, and one fails | bug — numbering is race-free (BUG-2427) | Claude, delegated (BUG-727 precedent) |
| P3 | The year in a return number comes from the server's local clock | bug — from UTC (BUG-2428) | Claude, delegated (BUG-1441 precedent) |
| D1 | Looking a return up by its credit note takes "the first" match with no order | intended — one return per credit note by construction | Claude, delegated |

Decided by house rules: an order's returns of the same creation time come back in no fixed order (BUG-2429); the open-returns list (BUG-2430) and a return's lines (BUG-2431) have no order at all.

### House-rule violations — applied automatically

- **HR-6** `get_by_purchase_order` R3 — ordered by `created_at` newest first, nothing after it. `created_at` is set in Python (`utcnow`), so two returns of one transaction or clock tick can tie. Verified under a forced sequential scan: four returns of one time came back `22581, 22582, 22585, 22587`, and after an update of `22581` as `22582, 22585, 22587, 22581`. This list is `GET /purchase-orders/{po_id}/returns/`. Intended: `created_at` newest first, then `id` descending (BUG-1442 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2429 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_by_purchase_order` R3.
- **HR-6** `get_open_by_purchase_order` R3 — no `ORDER BY`. Verified: three pending returns came back `22582, 22585, 22581`. The only caller turns the list into "is there any" (`has_open_return`), so no screen shows the order today; the method still returns a list. Intended: `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2430 (pattern `unordered-pagination`). Rules: `get_open_by_purchase_order` R3.
- **HR-6** `DAOPurchaseOrderReturnItem.get_by_return` R3 — no `ORDER BY`. Verified: three lines came back `22081, 22082, 22080` after the lowest was updated. The list numbers the credit-note invoice's lines (`line_number` 1, 2, 3 in list order) at `start_return`, and drives `complete_return`. Intended: `id` ascending, the order the lines were entered (BUG-1270 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2431 (pattern `unordered-pagination`). Rules: `get_by_return` R3.

Checked and **not** a new line here: **HR-4** — neither table, nor `purchase_orders`, has a soft-delete column; a voided return is a visible state, and every list returns it. **HR-5, HR-7, HR-8** — no method pages, no `LIKE` on user text (the numbering `LIKE` prefix is built by code from `PR-`, the year and `-`; none of them holds `%` or `_`). **HR-9** — `create_with_user` writes `created_by` only; `updated_by` is the callers'. **HR-10** — the DAO takes no lock; numbering is P2, and `complete_return` / `void_return` reading the status are the purchase order service's (not yet described, FU-1 (b)). **HR-15** — the DAO computes no money (`quantity_returned`, `unit_price` are stored by the inherited `create`). **HR-16** — every query filters on the row's own `workspace_id` (a line of workspace B on a return of A is not listed: `get_by_return` R2); `create_with_user` writes the workspace and order the caller passes, and `start_return` reads the purchase order with the workspace first. **HR-1, HR-2** — `reason`, `notes` are free text, not names (stored as given, `""` included).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-09)

### P1. A workspace cannot start its first return of the year if another workspace has that number — 🐞 BUG-2426
**Background:** A return's number is `PR-<year>-<n>`, where `<n>` is one more than the number of **this workspace's** returns of that year. The database requires each number to be unique across **all** workspaces (`purchase_order_returns_return_number_key`). The same was ruled a bug for order and delivery numbers (BUG-726).
**What happens today:** Workspace B's first return of 2026 is numbered `PR-2026-001`; if workspace A already has `PR-2026-001`, the insert fails with `IntegrityError` 23505 at flush. Every retry computes `PR-2026-001` again, so B cannot start any return that year until A's count and B's diverge. (Verified: 23505.)
**Example:** Workspace A has started 4 returns in 2026. Workspace B received a damaged batch and starts a return to the supplier and gets an error, every time, for the rest of the year.
**Rules affected:** `create_with_user` R4
**Answer:** bug — per BUG-726 precedent: return numbers are unique per workspace (unique index on `(workspace_id, return_number)` replacing the global one); every workspace starts at `-001`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09; workspace scoping): 🐞 BUG-2426 (pattern `unscoped-uniqueness-constraint`). Fix is a migration; the DAO's count is already per workspace. Rules: `create_with_user` R4 (tagged).

### P2. Two returns started at once in one workspace can get the same number — 🐞 BUG-2427
**Background:** The next number is the count of the year's returns plus one, computed with no lock or sequence.
**What happens today:** Two requests that count before either inserts get the same number; the second insert fails with `IntegrityError` 23505, a 500, and its whole `start_return` (credit note included) is rolled back. (Verified: two counts before an insert both gave `PR-2026-001`; after 999 returns the next is `PR-2026-1000`.)
**Example:** Two users of one workspace start returns on two different purchase orders in the same second. Both are given `PR-2026-007`; one return is saved, the other user gets an error and has to start it again.
**Rules affected:** `create_with_user` R3
**Answer:** bug — per BUG-727 precedent: numbering is race-free (a per-workspace, per-year counter read with a lock, or a retry on the unique violation); two concurrent creates both succeed with distinct numbers
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): 🐞 BUG-2427 (pattern `count-then-insert-race`). The count is otherwise sound: returns are never deleted (no delete path; `delete_purchase_order` refuses an order with receiving history, and a return needs received goods, so the cascade never removes a return), the number cannot be edited, voided returns still count, and the count is numeric, so `-999` is followed by `-1000`. Rules: `create_with_user` R3 (tagged; not unit-testable, no case).

### P3. The year in a return number comes from the server's local clock — 🐞 BUG-2428
**Background:** `create_with_user` takes the year from `datetime.now()`, the local time of the machine running the API; `created_at` and everything else is UTC (`utcnow`). The same was ruled a bug for batch and ticket numbers (BUG-1334, BUG-1441).
**What happens today:** On a server whose local clock is in another year than UTC, the return gets the other year. (Verified with a patched `datetime.now()` returning 1 January 2031 05:00: `PR-2031-001`.)
**Example:** A server set to `Asia/Dhaka` (UTC+6). A return started at 20:00 UTC on 31 December 2026 is numbered `PR-2027-001`, while its `created_at` says 2026.
**Rules affected:** `create_with_user` R2
**Answer:** bug — per BUG-1441 precedent: the year comes from `utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): 🐞 BUG-2428 (pattern `local-clock-instead-of-utc`). Rules: `create_with_user` R2 (tagged).

### New questions

### D1. Looking a return up by its credit note takes "the first" match — ✅ intended
**Background:** Starting a return creates its own credit-note invoice and stores it in the return's `invoice_id`; nothing else writes `invoice_id`. When a payment is recorded or voided on an invoice of type `purchase_order`, the invoice payment manager asks `get_by_invoice_id` whether that invoice is a return's credit note, and if so updates that return's `paid` flag. There is no unique index on `invoice_id`.
**What happens today:** The first row the database finds is returned, with no `ORDER BY`. With two returns on one invoice (verified only by setting it by hand) the lower id came back.
**Example:** No API path can give two returns the same credit note, so a payment on credit note `INV-…` always updates exactly the return that created it.
**Rules affected:** `get_by_invoice_id` R1, R3
**Suggested answer:** intended — one return per credit note holds by construction; a unique index can be added when the return flow is described (FU-1 (c)).
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-09; not money: which row is found, not what it holds)
**Resolution:** no bug. Rules: `get_by_invoice_id` R1 ✅, R3 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Purchase order service / return manager** (`app/services/purchase_order_service.py` return methods, `app/managers/purchase_order_return_manager.py`; no spec yet) | (a) The return response lists `ret.items`, the relationship, which has no `order_by` either: same fix as BUG-2431 (`order_by=PurchaseOrderReturnItem.id`) or the response reads `get_by_return`. (b) HR-10: `complete_return` and `void_return` read `status == 'pending'` and then move stock / void the credit note with no row lock; `start_return` checks available quantities with no lock either, so two returns at once can over-return a line. These touch stock and money: ask there. (c) A unique index on `invoice_id` (where not null) would make D1 enforced, not just true. (d) `validate_and_build_items` falls back to the order line's `unit_price` when the request sends none; the credit note's lines use `unit_price or 0`. Stock out on completion is `po_return_inventory` (approved spec). | reading the callers |
| FU-2 | **Purchase order manager** (`mark_order_complete`) | `has_open_return` treats only `status == 'pending'` as open (exact, lower-case); the code only ever writes `pending`, `completed`, `voided`, so nothing to change. Listed so the next describer does not re-check it. | `get_open_by_purchase_order` R1 |

## Overview
`DAOPurchaseOrderReturn` creates and reads `purchase_order_returns`, a batch of received goods sent back to the supplier (lifecycle `pending` → `completed` | `voided`), and `DAOPurchaseOrderReturnItem` reads its lines, `purchase_order_return_items`. Callers: `PurchaseOrderService.start_return` (`create_with_user`; inherited `create` for each line; `get_by_return` to build the credit note), `PurchaseOrderService.complete_return` (`get_by_return`), `PurchaseOrderReturnManager` (`get_open_by_purchase_order` through `has_open_return`, inherited `get_by_id_and_workspace` in `get_return`, `get_by_purchase_order` in `list_returns`), `InvoicePaymentManager._sync_linked_order` (`get_by_invoice_id`). Every method filters on the row's own `workspace_id`. It flushes only in `create_with_user`, never commits, and takes no lock.

**Callables:** 6 specified · 2 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** `datetime.now` in `app.dao.purchase_order_return` (patch the module's `datetime` name) for the year of `create_with_user` today. The intended code (R2, BUG fix) imports `utcnow` into the DAO module (`from app.utils.time import utcnow`, as the other DAOs do) and takes `utcnow().year`, so the intended patch target is `app.dao.purchase_order_return.utcnow` (patch with `create=True` until the fix adds the name). `created_at` is the model's own `utcnow` default, captured at import, and no patch reaches it.
**Integration-only behavior:** none.

**Model facts (table `purchase_order_returns`, class `app.models.purchase_order_return.PurchaseOrderReturn`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE, indexed | — |
| `purchase_order_id` | Integer NOT NULL, FK `purchase_orders.id` ON DELETE CASCADE, indexed | — |
| `return_number` | String(100) NOT NULL, **UNIQUE across all workspaces** (`purchase_order_returns_return_number_key`), indexed | — |
| `status` | String(20) NOT NULL, indexed, no check constraint; written values `pending`, `completed`, `voided` | `'pending'` (Python and database) |
| `return_type` | String(20) NOT NULL, no check constraint; `replace` / `refund` | database `'refund'` |
| `invoice_id` | Integer nullable, FK `account_invoices.id` ON DELETE SET NULL, indexed, not unique | `NULL` |
| `paid` | Boolean NOT NULL | `False` (Python), `false` (database) |
| `reason`, `notes` | Text nullable | `NULL` |
| `completed_at` | `timestamp` (no time zone) nullable | `NULL` |
| `completed_by`, `updated_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_by` | Integer **NOT NULL**, FK `profiles.id` ON DELETE SET NULL, indexed | — |
| `created_at` | `timestamp` (no time zone) NOT NULL | Python `utcnow` (naive UTC); database `now()` unused by the ORM |
| `updated_at` | `timestamp` nullable | `NULL`; Python `onupdate` `utcnow` |

**Model facts (table `purchase_order_return_items`, class `PurchaseOrderReturnItem`):** `id` PK; `workspace_id` NOT NULL FK workspaces CASCADE; `return_id` NOT NULL FK `purchase_order_returns.id` ON DELETE CASCADE; `po_item_id` NOT NULL FK `purchase_order_items.id` ON DELETE RESTRICT; `item_id` **NOT NULL** FK `items.id` RESTRICT; `quantity_returned` Numeric(15,2) NOT NULL; `unit_price` Numeric(15,2) nullable; `notes` Text nullable. No soft delete on either table. Properties `item_name` (catalog item's name, else `None`) and `item_unit` (catalog item's unit, else `None`) are not DAO behaviour.

**Notes for the test designer:**
- Return rows need a `purchase_orders` row and a profile for `created_by`; lines need a `purchase_order_items` row and an `items` row. Rows of another workspace on one order are invalid data (HR-16) and can only be made by inserting directly.
- Ties on `created_at`: insert rows then set one `created_at` by SQL; under `SET LOCAL enable_indexscan = off` (and bitmap / index-only) an update of the lowest id moves it last in physical order, which shows the missing tie-break.
- `create_with_user` flushes, so `IntegrityError` surfaces from the call itself; wrap it in a savepoint to continue.
- **Parent rows (from the models, 2026-11-10):** `purchase_orders` (`app.models.purchase_order.PurchaseOrder`) needs `workspace_id`, `po_number`, `destination_type`, `destination_id`, `current_status_id`, `created_by` (everything else, supplier included, is nullable or has a default); `statuses` (`app.models.status.Status`) `workspace_id`, `name`, `comment`; `purchase_order_items` (`app.models.purchase_order_item.PurchaseOrderItem`) `workspace_id`, `purchase_order_id`, `line_number`, `item_id`, `quantity_ordered`; `items` (`app.models.item.Item`) `workspace_id`, `name`, `name_normalized`, `unit`; `account_invoices` (`app.models.account_invoice.AccountInvoice`) `workspace_id`, `account_id`, `invoice_type`, `invoice_amount`, `invoice_date` (and `accounts` `workspace_id`, `name`). Return lines are `app.models.purchase_order_return.PurchaseOrderReturnItem`.
- **A real voided return** (`void_return` in `app/services/purchase_order_service.py`) has: `status = 'voided'`; `paid` re-synced from its credit note (`False` unless that invoice's `payment_status` is `'paid'`); `updated_at` set by the column's `onupdate` (naive UTC); `completed_at`, `completed_by` stay `NULL`; `updated_by` is **not** written (the service sets no user; noted as a follow-up for the return service spec, not a rule here). Its credit note is voided by the invoice manager. A completed return has `status = 'completed'`, `completed_at = utcnow()`, `completed_by = user`.

## Not specified
- `purchase_order_return_dao`, `purchase_order_return_item_dao` — module singletons, no logic.
- Inherited `BaseDAO` methods of both classes — `tests/unit/dao/base.spec.md`.

---

## `DAOPurchaseOrderReturn.generate_return_number(db, *, workspace_id, year)`
**Shape:** compute
**Persistence:** reads
**Visibility:** internal (used by: `create_with_user`)

**Purpose:** The next return number of a workspace for a year.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | Only this workspace's returns are counted; not checked to exist. |
| `year` | int | Put into the number as written (`1` → `PR-1-…`); not range-checked. |

**Returns:** `str` `PR-<year>-<n>`, `<n>` zero-padded to at least 3 digits.

**Rules:**
- **R1.** `<n>` is the number of this workspace's returns whose `return_number` starts with `PR-<year>-`, plus one: no rows → `PR-2026-001`; one → `PR-2026-002`.
- **R1a.** The prefix match is case-sensitive (`LIKE`): a hand-made `pr-2026-001` is not counted. Intended (decided under the reviewer's delegation, 2026-11-10): numbers are made only here, always upper-case, and cannot be edited, so a lower-case number is foreign data (same decision as the sales order and delivery DAOs).
- **R2.** Every status counts (`pending`, `completed`, `voided`), and so does any row with the prefix whatever follows it (a hand-made `PR-2026-XYZ` counts as one).
- **R3.** Another workspace's returns are not counted: workspace B gets `PR-2026-001` while workspace A has three. Other years are not counted (`PR-2099-001` while 2026 has rows).
- **R4.** Padding is a minimum of 3 digits: count 9 → `-010`, count 999 → `-1000`.
- **R5.** Nothing is written.

**Errors:** none.
**Side effects:** none.

---

## `DAOPurchaseOrderReturn.create_with_user(db, *, workspace_id, purchase_order_id, user_id, return_type, reason=None, notes=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `PurchaseOrderService.start_return`)

**Purpose:** Create a new pending return with the next number.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | Stored; the number is counted in it. |
| `purchase_order_id` | int | Stored as given; not checked against the workspace here (the caller reads the order with the workspace first). An id with no order fails the FK at flush. |
| `user_id` | int | Stored as `created_by`; `None` fails NOT NULL at flush (`IntegrityError` 23502). |
| `return_type` | str | Stored as given; no check here or in the database (`"banana"` is stored). The schema `PurchaseOrderReturnCreate` allows only `replace` / `refund`. |
| `reason`, `notes` | str \| None | Stored as given (`""` stays `""`), default `None`. |

**Returns:** the new `PurchaseOrderReturn`, flushed (has `id`), not committed.

**Rules:**
- **R1.** The row has `workspace_id`, `purchase_order_id`, `return_type`, `reason`, `notes` as given, `created_by = user_id`, `status = 'pending'`, `paid = False`, `invoice_id`, `completed_at`, `completed_by`, `updated_by`, `updated_at` all `NULL`, and `created_at` = `utcnow()` at flush.
- **R2.** [BUG-2428] The number's year is the current **UTC** year. *(Today: `datetime.now().year`, the server's local clock; a patched `datetime.now()` of 2031-01-01 05:00 gave `PR-2031-001`.)*
- **R2a.** The number is `generate_return_number` R1–R4 for that workspace and year (empty workspace → `PR-<year>-001`, next → `-002`).
- **R3.** [BUG-2427] Two creates in one workspace at the same time both succeed, with distinct numbers. *(Today: both count before either inserts, get the same number, and the second fails with `IntegrityError` 23505.)* Not unit-testable (two transactions); no case.
- **R4.** [BUG-2426] A workspace's first return of a year succeeds as `PR-<year>-001` even when another workspace already has `PR-<year>-001`; the same number is refused only within one workspace (`IntegrityError` 23505). *(Today: the unique index is global, so workspace B's `PR-2026-001` fails with 23505 while A has it.)* Fix: a migration (unique `(workspace_id, return_number)`).
- **R3a.** [BUG-2427] (decided under the reviewer's delegation, 2026-11-10) `create_with_user` never hands out a number already used in its workspace: with hand-made `PR-2026-001`, `-002`, `-004` (count 3, so today's next number `-004` is taken) the call succeeds with a free number (`-005` under a highest-plus-one counter; the card asserts only "succeeds, number unused in the workspace, starts `PR-2026-`"). *(Today: it fails with `IntegrityError` 23505.)* Why: the race fix makes the number come from a counter or a retry, and either way the stated intent of BUG-2427 is "both creates succeed with distinct numbers"; a gap can only come from hand-made data (returns are never deleted or renumbered). The database fact in R4 — a second row with the same number in one workspace is refused with 23505 — stays true under every fix and is tested by inserting the row directly, not through this call.
- **R5.** The row is flushed, not committed; an integrity failure (R3, R4, `user_id=None`, unknown order) raises from this call and the session needs a rollback.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| number already used (R3, R4 today; same workspace after the fix) | `sqlalchemy.exc.IntegrityError` (23505) | database message |
| `user_id is None` | `IntegrityError` (23502) | database message |
| unknown `purchase_order_id` / `workspace_id` | `IntegrityError` (23503) | database message |

**Side effects:** one `purchase_order_returns` row; flush.

---

## `DAOPurchaseOrderReturn.get_by_purchase_order(db, *, purchase_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderReturnManager.list_returns` → `GET /purchase-orders/{po_id}/returns/`)

**Purpose:** All returns of one order.

**Inputs:** `purchase_order_id`, `workspace_id` — ints, not checked to exist.

**Returns:** `list[PurchaseOrderReturn]`, possibly empty.

**Rules:**
- **R1.** Every return of this order in this workspace is returned, whatever its status (`pending`, `completed`, `voided`). No paging.
- **R2.** A return of the same order id under another workspace is not returned; an order with no returns, an unknown order, or the right order with another workspace's id → `[]`.
- **R3.** [BUG-2429] Newest `created_at` first, then `id` descending. *(Today: `created_at` descending only; returns of one `created_at` come back in no fixed order — verified `22581, 22582, 22585, 22587` then `22582, 22585, 22587, 22581` after an update.)*

**Errors:** none. **Side effects:** none.

---

## `DAOPurchaseOrderReturn.get_open_by_purchase_order(db, *, purchase_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** internal (used by: `PurchaseOrderReturnManager.has_open_return` → `PurchaseOrderManager.mark_order_complete`)

**Purpose:** The order's returns still pending.

**Inputs:** as `get_by_purchase_order`.

**Returns:** `list[PurchaseOrderReturn]`, possibly empty.

**Rules:**
- **R1.** Only returns with `status` exactly `'pending'` are returned; `completed` and `voided` are not, and neither is a hand-set `'Pending'` (case-sensitive).
- **R2.** Workspace and order scoping as `get_by_purchase_order` R2.
- **R3.** [BUG-2430] `id` ascending. *(Today: no `ORDER BY`; verified `22582, 22585, 22581`.)*

**Errors:** none. **Side effects:** none.

---

## `DAOPurchaseOrderReturn.get_by_invoice_id(db, *, invoice_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** internal (used by: `InvoicePaymentManager._sync_linked_order`)

**Purpose:** The return whose credit note is this invoice.

**Inputs:** `invoice_id`, `workspace_id` — ints.

**Returns:** `PurchaseOrderReturn | None`.

**Rules:**
- **R1.** The return of this workspace with `invoice_id` equal to the given id is returned, whatever its status. ✅
- **R2.** No such return (an order's own invoice, an unknown id, or the return belongs to another workspace) → `None`.
- **R3.** Several returns on one invoice cannot arise through the API (D1); if present, one of them is returned. ✅ Do not test which.
- **R4.** `invoice_id=None` is compared as `IS NULL`: it returns a return of this workspace that has no credit note (possible only when that invoice was deleted, `ON DELETE SET NULL`), or `None` when every return has one. Decided under the reviewer's delegation (2026-11-10): intended as is, no bug — the parameter is an `int`, both callers (`InvoicePaymentManager`, with the id of an invoice it has just loaded) never pass `None`, and the sales order DAO's `get_by_invoice_id` R4 says the same. A card pins it so a change is noticed.

**Errors:** none. **Side effects:** none.

---

## `DAOPurchaseOrderReturnItem.get_by_return(db, *, return_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** internal (used by: `PurchaseOrderService._attach_return_invoice_for_po`, `PurchaseOrderService.complete_return`)

**Purpose:** The lines of one return.

**Inputs:** `return_id`, `workspace_id` — ints, not checked to exist.

**Returns:** `list[PurchaseOrderReturnItem]`, possibly empty.

**Rules:**
- **R1.** Every line with this `return_id` and this `workspace_id` is returned; no paging. (`item_id` is NOT NULL on this table: every line names a catalog item.)
- **R2.** A line of another workspace on the same return is not returned (invalid data, HR-16); unknown return → `[]`.
- **R3.** [BUG-2431] `id` ascending. *(Today: no `ORDER BY`; verified `22081, 22082, 22080` after the lowest was updated, so credit-note line numbers follow physical order.)*

**Errors:** none. **Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20–27 | count rows of workspace with prefix (0 / many; any status; any suffix) | `generate_return_number` R1, R2, R3 |
| 28 | `{count + 1:03d}` padding (< 1000 / ≥ 1000) | `generate_return_number` R4 |
| 32 | `reason`, `notes` default `None` / given | `create_with_user` R1 |
| 34–36 | year from `datetime.now()` | `create_with_user` R2, R2a |
| 37–46 | fixed `status='pending'`, `created_by` | `create_with_user` R1 |
| 48 | flush: ok / 23505 / 23502 / 23503 | `create_with_user` R3, R4, R5 |
| 55–59 | filter order + workspace | `get_by_purchase_order` R1, R2 |
| 60 | `ORDER BY created_at DESC` (ties) | `get_by_purchase_order` R3 |
| 67–74 | filter order + workspace + `status == 'pending'`, no order | `get_open_by_purchase_order` R1–R3 |
| 80–87 | filter invoice + workspace; `.first()` found / `None` | `get_by_invoice_id` R1–R3 |
| 96–103 | filter return + workspace, no order | `get_by_return` R1–R3 |

## Gap log
- G1 (purchase_order_return.cases.md gap 3) — Fact — Notes for the test designer: parent tables' required columns and model modules, return lines' class and module, from the models (2026-11-10).
- G2 (purchase_order_return.cases.md gap 4) — Fact — Notes: the columns a real void (and a completion) writes, from `void_return` / `complete_return`; `updated_by` is not written on void.
- G3 (purchase_order_return.cases.md gap 2) — Fact / decision — Externals: the intended year comes from `app.dao.purchase_order_return.utcnow` (patch target, `create=True` until the fix).
- G4 (coordinator; twin of sales gap 3) — Intent, decided under delegation (2026-11-10) — new `create_with_user` R3a [BUG-2427]: after the race fix a taken next number never fails the call; R4's 23505 stays as a direct-insert database fact.
- G5 (coordinator; twin of sales gap 4) — Intent, decided under delegation (2026-11-10) — new `get_by_invoice_id` R4: `None` matches a return with no credit note (`IS NULL`); intended, unreachable from the callers.
- G6 (purchase_order_return.cases.md gap 1) — Intent, decided under delegation (2026-11-10) — new `generate_return_number` R1a: case-sensitive prefix, intended.
