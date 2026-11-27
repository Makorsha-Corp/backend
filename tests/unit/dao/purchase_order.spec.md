# Spec — `app/dao/purchase_order.py`

> **Status:** APPROVED (2026-11-11; nothing open — the owner answered OQ-35 … OQ-38 on 2026-11-11: BUG-2639, BUG-2640, BUG-2641; OQ-36 intended. The case designer's 6 gaps are closed, Gap log at the end.)
> **Source commit:** e48a092

> **Review round 2026-11-10 (describe).** **Delegated:** every house-rule line, P1–P4 and Q1 were decided by Claude under the reviewer's delegation (2026-11-10); none is the owner's own answer. **Owner (pending, not blocking):** OQ-35 … OQ-38, parked in `docs/testing/owner-questions.md`: they decide what a money or stock figure *should* be, so the rules are written to today's behaviour and tested to it until the owner answers.

> **Review round 2026-11-11 (apply-review + fill-gaps).** **Owner (2026-11-11):** OQ-35 bug as suggested → 🐞 BUG-2639; OQ-36 intended (no bug); OQ-37 bug as suggested → 🐞 BUG-2640; OQ-38 bug, owner's own wording ("7 received of 10 ordered · 3 refunded"; a line is done when received + refunded = ordered) → 🐞 BUG-2641. This DAO's part is to return the refunded total next to ordered and received; the wording and the "done" test belong to the service / web app (FU-5). **Delegated (2026-11-11):** how a test reaches "1000 numbers taken" once BUG-2630 is fixed (G3). **Gaps:** all 6 closed, from the code (G1, G2, G4, G5, G6) or by delegation (G3). Two facts found while closing them correct earlier wording: project components are hard-deleted, not soft-deleted (`_apply…` R6), and a real invoice void resets `payment_status` to `unpaid` (OQ-37 Background).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated (inherited `create`, `update`, `get`, `get_multi` are used by `PurchaseOrderManager`, `PurchaseOrderReturnManager` and the services).
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` on a paged or top-N result is a bug, and no order counts as deterministic unless it ends in `id` (HR-6, BUG-978 / BUG-2441). Raw lookups stay raw (HR-4 scope; `purchase_orders` has no soft-delete column — `voided` is a business state, not a delete). HR-15: money rounds half away from zero (the `Numeric(15, 2)` columns do it; verified `1.005` → `1.01`, `-1.005` → `-1.01`). HR-16: nothing crosses workspaces. Stage names are compared by exact spelling today — that is BUG-1881 (owner, OQ-13), reused here, not re-logged. Hub "recent" ordering follows BUG-746 (expense hub) and an unknown `invoice_filter` value meaning "no filter" follows the approved expense manager spec (`list_expense_orders_for_hub` R6).
>
> **Verified by running** (my own throwaway scripts `schema.py`, `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdao\purchase_order\`, one transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing committed): the tables' columns, defaults, constraints and indexes (`uq_po_workspace_number` UNIQUE `(workspace_id, po_number)` — **per workspace**; no global unique index on `po_number`, only a plain index); numbering in an empty workspace (`PO-2026-001`), with another workspace holding `PO-2026-001` (`PO-2026-002` — skipped), with `PO-2026-abc` only (`…-002` because of the other workspace; the suffix is ignored), after `PO-2026-007` (`…-008`), with `PO-2026-1-2` (still `…-008`), after `PO-2026-9999` (`…-10000`), with a patched `datetime.now()` (1 January 2031 → `PO-2031-001`); a duplicate number in one workspace (23505 `uq_po_workspace_number`) and the same number in another workspace (accepted); hub list / count / stats / recent / highlights with every filter, including `exclude_complete=True` together with the highlights' own status join (works, no duplicate-join error), `%` and `_` searches (match everything), `outstanding_payment` (included a draft and a voided invoice), recent ordering (the one order with `updated_at` came **last**); stats `(6, 1006.00, 5, 906.00, 3)` with a voided 400.00 order counted open; `get_by_invoice_id` across workspaces; item summary, previews (empty name → `Item #<id>`, limit 2, limit 0), `get_by_order` with two lines numbered 1 (returned higher `id` first). **Read, not run:** `PurchaseOrderManager`, `PurchaseOrderService` (`list_purchase_orders_page`, `get_purchase_order_hub_stats`, `_attach_item_summaries`), `InventoryManager.get_incoming_summary_for_factory`, `GET /purchase-orders/`, `GET /purchase-orders/stats/`, the web app's PO hub (`purchaseOrderHubApiParams.ts`, `PurchaseOrdersPage.tsx`, `PurchaseOrderListRow.tsx`). **Not run:** anything over HTTP; two concurrent transactions.

## Review
> Delegated items decided 2026-11-10; owner questions parked (not blocking).

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A workspace's PO numbers skip any number another workspace already uses | bug — each workspace numbers on its own (BUG-2630) | Claude, delegated |
| P2 | Two POs created at once in one workspace can get the same number; the second fails | bug — race-free (BUG-2631) | Claude, delegated |
| P3 | The year in a PO number comes from the server's local clock | bug — UTC (BUG-2632) | Claude, delegated |
| P4 | "Recent orders" and the pending samples put never-edited orders first | bug — by last activity (BUG-2635) | Claude, delegated |
| Q1 | `get_by_workspace` and `get_next_number` have no caller | remove | Claude, delegated |
| OQ-35 | Hub money totals add voided orders when "show voided" is on, and count them as open | bug — voided orders add no money and are not open (BUG-2639) | owner, 2026-11-11 |
| OQ-36 | "Open value" is the full total of every order not both Complete and paid | intended | owner, 2026-11-11 |
| OQ-37 | "Outstanding payment" filter includes orders whose invoice is a draft or voided | bug — only confirmed or locked invoices not fully paid (BUG-2640) | owner, 2026-11-11 |
| OQ-38 | The list's "7/10 received" ignores refunded quantities | bug — show ordered, received and refunded; done when received + refunded = ordered (BUG-2641) | owner, 2026-11-11 |

Decided by house rules: search wildcards (BUG-2633), search matching a deleted supplier (BUG-2634), oldest-drafts ties (BUG-2636), PO found for an invoice is arbitrary (BUG-2637), item-name preview ties (BUG-2638).
Already decided elsewhere and reused: stage names compared by exact spelling (BUG-1881, owner OQ-13); voided orders in the stock page's incoming list are the inventory manager's job (BUG-717).

### House-rule violations — applied automatically

- **HR-8** `_apply_purchase_order_hub_filters` R11 — search text is put into `ILIKE '%…%'` unescaped: verified `_` and `%` each return every order. Intended: `%`, `_` and `\` match literally (BUG-745 precedent).
**Answer:** bug — per HR-8 (house rule)
**Resolution:** 🐞 BUG-2633 (pattern `unescaped-like-wildcards`). Rule: `_apply_purchase_order_hub_filters` R11.
- **HR-4** `_apply_purchase_order_hub_filters` R12 — the supplier-name search matches a soft-deleted account. The web app's hub shows such a row as `Account #<id>` (its account list leaves deleted accounts out), so the user searches for a name the row does not show. Intended: a deleted supplier's name does not match; the PO is still found by its number.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-2634 (pattern `join-ignores-soft-deleted`). Rule: `_apply_purchase_order_hub_filters` R12.
- **HR-6** `get_pending_highlights_for_hub` R5 — "oldest drafts" (top 5) is ordered by `created_at` only. Intended: `created_at` ascending, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2636 (pattern `unordered-pagination`). Rule: `get_pending_highlights_for_hub` R5.
- **HR-6** `get_by_invoice_id` R3 — `.first()` with no `ORDER BY`. `invoice_id` is not unique and `PurchaseOrderUpdate` carries `invoice_id`, so two POs can point at one invoice (verified a second PO on the same invoice stored). Through `PurchaseOrderManager.get_po_by_invoice_id` the PO kept in step with invoice payments is then arbitrary. Intended: the lowest `id` (BUG-2441 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2637 (pattern `unordered-pagination`). Rule: `get_by_invoice_id` R3.
- **HR-6** `PurchaseOrderItemDAO.preview_names_by_purchase_order_ids` R3 — the first N names per order are taken by `line_number` with no `id` tie-breaker; two lines with the same number (verified possible: no unique constraint; `add_item` numbers lines max + 1 without a lock) give an unstable preview. Intended: `line_number`, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2638 (pattern `unordered-pagination`). Rule: `preview_names_by_purchase_order_ids` R3.

Checked and **not** a new line here: **HR-4** for the orders themselves — no soft-delete column; voided orders are filtered by `exclude_voided` where the caller asks. Machines and project components in the factory filter are matched whether deleted or not: the filter asks "which factory is this PO for", and a PO for a since-deleted machine still belongs to that factory (decided under the delegation). **HR-5** — every filter is in SQL before `skip` / `limit`; the count uses the same filters. **HR-6** for `list_for_hub` (`created_at` desc, `id` desc — stable); `list_for_destination`, `get_by_order`, `get_by_purchase_order_ids` are neither paged nor top-N (full lists). **HR-7** — the endpoint has `limit` `ge=1, le=100`, `skip` `ge=0`. **HR-9** — no audit stamps written here. **HR-10** — this DAO only reads, apart from numbering (P2); the PO manager's state changes must read the row `FOR UPDATE`, which this DAO cannot do today (FU-1). **HR-15** — totals and quantities are `Numeric(15, 2)` and the sums are done in SQL, no Python rounding. **HR-16** — every query filters on the row's own `workspace_id`, and the factory filter's machine / component sub-queries filter on the workspace too; the one cross-workspace effect is numbering (P1).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-10)

### P1. A workspace's PO numbers skip numbers another workspace uses — 🐞 BUG-2630
**Background:** PO numbers look like `PO-2026-001`. The database already keeps them unique **per workspace** (`uq_po_workspace_number`). Before using a number, `allocate_po_number` checks whether **any** workspace has it ("legacy global-unique constraint", says the docstring; no such constraint exists any more).
**What happens today:** The next number is this workspace's highest + 1, then bumped past every number another workspace holds. Verified: workspace B holds `PO-2026-001`; workspace A's first PO is `PO-2026-002`.
**Example:** Company A starts using the app in March after twenty other companies. Its first purchase order is `PO-2026-014`, not `-001`, and the gap depends on other customers' data.
**Rules affected:** `allocate_po_number` R5
**Answer:** bug — per BUG-726 / BUG-749 precedent: numbers are unique per workspace only; every workspace starts at `-001`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2630 (pattern `unscoped-uniqueness-check`; HR-16 — another workspace's rows must not affect this one). Rules: `allocate_po_number` R5 (tagged).

### P2. Two POs created at once can get the same number — 🐞 BUG-2631
**Background:** The number is computed by reading the workspace's numbers, with no lock or counter; the row is inserted later by the manager.
**What happens today:** Two creates in one workspace at the same moment both compute `PO-2026-008`; the second fails at flush on `uq_po_workspace_number` (`IntegrityError` → 500) and the user's order is lost.
**Example:** Two buyers press "Create PO" within the same second; one of them gets an error page.
**Rules affected:** `allocate_po_number` R7
**Answer:** bug — per BUG-727 / BUG-749 precedent: number assignment is race-safe (per-workspace, per-year counter read `FOR UPDATE`, or retry on unique violation); both creates succeed with distinct numbers
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2631 (pattern `unsafe-sequence-generation`). The race half is integration-only. Rules: `allocate_po_number` R7 (tagged).

### P3. The year in a PO number comes from the server's local clock — 🐞 BUG-2632
**Background:** `allocate_po_number` takes the year from `datetime.now()`; `created_at` and everything else is UTC.
**What happens today:** Verified with a patched `datetime.now()` returning 1 January 2031 00:30: `PO-2031-001`.
**Example:** A server set to `Asia/Dhaka`: a PO saved at 20:00 UTC on 31 December 2026 is numbered `PO-2027-001` while its `created_at` says 2026.
**Rules affected:** `allocate_po_number` R1
**Answer:** bug — per BUG-1334 / BUG-2440 precedent: the year comes from `utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2632 (pattern `local-clock-instead-of-utc`). Rules: `allocate_po_number` R1 (tagged).

### P4. "Recent orders" and the pending samples show never-edited orders first — 🐞 BUG-2635
**Background:** `updated_at` is empty until a PO is first edited. Postgres sorts empty values **first** when sorting newest-first.
**What happens today:** `list_recent_for_hub` sorts by `updated_at` desc, then `created_at` desc; the "pending planning" and "missing invoice" samples sort by `updated_at` desc alone. Verified: of six orders, the only one edited (today) came **last** in "recent".
**Example:** 50 old POs never touched since creation and 5 edited today: the hub's "Recent" panel (10 rows) shows 10 of the old untouched ones and none of today's edits.
**Rules affected:** `list_recent_for_hub` R1, `get_pending_highlights_for_hub` R2, R3
**Answer:** bug — per BUG-746 precedent: order by `coalesce(updated_at, created_at)` desc, then `id` desc
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2635 (pattern `unordered-pagination`; one bug for the three places). Rules: `list_recent_for_hub` R1, `get_pending_highlights_for_hub` R2, R3 (tagged).

### New questions

### Q1. `get_by_workspace` and `get_next_number` have no caller — 🗑️ removed
**Background:** `get_by_workspace` (filters by supplier / invoice, newest first, 100 per page) is reached only through `PurchaseOrderManager.list_purchase_orders`, which nothing calls: `GET /purchase-orders/` goes through `list_for_hub`. `get_next_number` is an alias of `allocate_po_number` that nothing calls.
**What happens today:** No code in `app/`, `tests/` or `scripts/` reaches either. (`get_by_workspace` also uses a truthiness check — `account_id=0` means "no filter" — and has no `id` tie-breaker; both disappear with it.)
**Example:** Deleting both (and the manager's `list_purchase_orders`) changes no API response. Generic callers then get `BaseDAO.get_by_workspace` (`id` ascending), of which there are none today.
**Rules affected:** none (moved to Not specified)
**Answer:** remove — per the sales order DAO precedent (Q1): no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): both go under **Not specified** as dead code and into `docs/testing/dead-code-removal-checklist.md` (with `PurchaseOrderManager.list_purchase_orders`). No bug ID.

### Owner questions — answered by the owner, 2026-11-11 (`docs/testing/owner-questions.md`)

### OQ-35. Hub money totals add voided orders, and count them as open — 🐞 BUG-2639
**Background:** The PO hub's tiles show total count, total value, open count, open value and "not invoiced". With the hub's "show voided" switch on, the web app sends `exclude_voided=false`; the totals then cover voided orders too. Elsewhere voided orders count in no money figure (BUG-2500 orders overview, BUG-2521 item summary).
**What happens today:** A voided order adds its `total_amount` to total value **and**, since it is not "Complete and paid", to open count and open value. Verified: orders 100 (Complete, paid), 200 (Complete, unpaid), 300, 400 (voided), 1, 5 → `total_value 1006.00`, `open_count 5`, `open_value 906.00`.
**Example:** A 400,000.00 PO is voided by mistake-correction; the buyer switches on "show voided" to find it, and "Open value" jumps by 400,000.00.
**Suggested answer:** bug — voided orders add nothing to total value, open count or open value (they still count in total count and "not invoiced" when shown, matching the list).
**Rules affected:** `aggregate_hub_stats` R2, R3a, R3b
**Answer:** owner, 2026-11-11: bug — suggested answer.
**Resolution:** 🐞 BUG-2639 (pattern `voided-record-not-excluded`, as BUG-2500 / BUG-2521). Voided POs add nothing to `total_value`, `open_count` or `open_value`; they still count in `total_count` and `not_invoiced_count` when the filters keep them. Rules: `aggregate_hub_stats` R2, R3a (tagged), R3b.

### OQ-36. "Open value" is the full order total of every order not both Complete and paid — ✅ intended
**Background:** An order is "fully closed" when its stage is `Complete` **and** its `paid` flag is set (the web app's `isPurchaseOrderFullyClosed`). Everything else is "open".
**What happens today:** Open value adds the whole `total_amount` of each open order: a Complete order whose invoice is half paid adds its full total; a fully paid order still in `Receiving` adds its full total too.
**Example:** PO of 10,000.00, goods all received, 9,000.00 paid: open value shows 10,000.00, not the 1,000.00 still owed.
**Suggested answer:** intended — open value is the value of orders not yet closed (received **and** paid), at full order total; amounts still owed belong to the invoice / payables views.
**Alternatives:** (a) bug — open value is the unpaid balance of the linked invoice (order total when there is no invoice).
**Rules affected:** `aggregate_hub_stats` R3
**Answer:** owner, 2026-11-11: intended — open value is the full order total of orders not yet closed.
**Resolution:** no bug. Rules: `aggregate_hub_stats` R3 ✅.

### OQ-37. The "outstanding payment" filter includes orders whose invoice is a draft or voided — 🐞 BUG-2640
**Background:** An invoice's `payment_status` is `unpaid` from the moment it is created (default), and is only meaningful once the invoice is confirmed. *(Corrected 2026-11-11, G5: a real invoice void resets `payment_status` to `unpaid` and `paid_amount` to 0.00, so every voided invoice reads as unpaid.)*
**What happens today:** `invoice_filter=outstanding_payment` keeps orders whose invoice's `payment_status` is anything but `paid`, whatever the invoice's own status. Verified: a PO with a **draft** invoice and a PO with a **voided** invoice were both listed as outstanding.
**Example:** A buyer filters "outstanding payment" to see what the company still owes; a PO whose invoice was voided last month (nothing owed) is in the list.
**Suggested answer:** bug — an order is outstanding when its invoice is not voided and not draft (confirmed or locked) and `payment_status` is not `paid`. (The expense hub's unpaid pipeline already leaves voided invoices out.)
**Alternatives:** (a) leave drafts in, take only voided out (exactly the expense hub's rule).
**Rules affected:** `_apply_purchase_order_hub_filters` R9
**Answer:** owner, 2026-11-11: bug — suggested answer (only orders with a confirmed or locked invoice that is not fully paid).
**Resolution:** 🐞 BUG-2640 (pattern `unconfirmed-invoice-counted-outstanding`, new). Rules: `_apply_purchase_order_hub_filters` R9 (tagged).

### OQ-38. The list's "received" progress ignores refunded quantity — 🐞 BUG-2641
**Background:** A refund-type return bumps a line's `quantity_refunded`; that quantity is settled and will never be received. The order counts as fully received when received + refunded reaches the ordered quantity. The hub row shows "`received`/`ordered` received" while the order is in `Receiving`, from per-order sums of the lines (units of different items are added together).
**What happens today:** The sums are plain `quantity_ordered` and `quantity_received`. Verified: lines 10 ordered / 7 received / 3 refunded, 5.5 / 0 / 0 and 1 / 1 / 0 → ordered total 16.50, received total 8.00.
**Example:** 10 bolts ordered, 7 arrived, 3 refunded: nothing more is coming, but the row reads "7/10 received" until someone completes the order.
**Suggested answer:** bug — the ordered total counts each line as ordered − refunded (the row reads "7/7 received"); received stays the received quantity.
**Alternatives:** (a) intended — show raw ordered and received. (b) received total = received + refunded ("10/10").
**Rules affected:** `summarize_by_purchase_order_ids` R2, R2a
**Answer:** owner, 2026-11-11: bug — show all three numbers, e.g. "7 received of 10 ordered · 3 refunded"; a line counts as done when received + refunded = ordered.
**Resolution:** 🐞 BUG-2641 (pattern `refunded-quantity-ignored`). This DAO's part: each order's summary also carries `quantity_refunded_total`; ordered and received stay the raw sums (10 and 7 in the example; the suggested "ordered − refunded" is not what the owner chose). The wording and the "done" test (received + refunded = ordered) are the service's / web app's job (FU-5). Rules: `summarize_by_purchase_order_ids` R2 ✅ (today's sums stay right), R2a (tagged).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Purchase order manager** (`app/managers/purchase_order_manager.py`, not yet specified) | HR-10: receive, void, complete, reopen, set-approval and invoice-link check the PO's state and then change it, reading it with this DAO's `get_by_id_and_workspace`, which takes no lock. A `FOR UPDATE` read is needed there (new option or a manager query). | HR-10 check |
| FU-2 | **Purchase order manager / service** | `PurchaseOrderUpdate` includes `invoice_id`; check whether a client can link any invoice (another order's, another workspace's — HR-16) — cause of two POs on one invoice (BUG-2637). Compare BUG-1019 / BUG-2404 (sales: system-only). | `get_by_invoice_id` R3 |
| FU-3 | **Purchase order manager** | `add_item` / `replace_items` number lines max + 1 with no lock: concurrent adds can give two lines the same `line_number` (BUG-727 family). | `preview_names_by_purchase_order_ids` R3 |
| FU-4 | **Purchase order manager** | After BUG-2630 / BUG-2631 the manager must handle a unique violation on create (retry or counter) and must not depend on `allocate_po_number`'s 1000-attempt loop. | P1, P2 |
| FU-5 | **Purchase order service** (`_attach_item_summaries`, hub list response) **and web app** (`PurchaseOrderListRow.tsx`) | BUG-2641: pass `quantity_refunded_total` through; the row reads "7 received of 10 ordered · 3 refunded"; a line counts as done when received + refunded = ordered. The service spec carries that rule under BUG-2641. | OQ-38 |

## Overview
`PurchaseOrderDAO` reads `purchase_orders` for the PO hub (list, count, KPI stats, recent orders, pending highlights), for stock (orders for a destination) and for invoice syncing, and allocates PO numbers. `PurchaseOrderItemDAO` reads `purchase_order_items` (lines of one order, of many orders, per-order summaries and name previews). Callers: `PurchaseOrderManager` (`allocate_po_number` from `create_purchase_order`; hub methods; `get_by_invoice_id` from `get_po_by_invoice_id`; `get_by_id_and_workspace` and the item DAO everywhere), `PurchaseOrderService` (`list_purchase_orders_page` ← `GET /purchase-orders/`, `get_purchase_order_hub_stats` ← `GET /purchase-orders/stats/`, `_attach_item_summaries`, `list_for_destination`), `InventoryManager.get_incoming_summary_for_factory` (`list_for_destination`, `get_by_purchase_order_ids`), `PurchaseOrderReturnManager` (item DAO), `AttachmentManager` (`get_by_id_and_workspace`). It never writes, flushes or commits, and takes no lock.

**Callables:** 18 specified · 2 not specified as dead code (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** the clock of `allocate_po_number` — it imports `datetime` inside the function at call time, so patch `datetime.datetime` in the `datetime` module (e.g. `mock.patch("datetime.datetime", Fake)`); after BUG-2632 patch `app.dao.purchase_order.utcnow` (`create=True`: not imported today) and `app.utils.time.utcnow`.
**Integration-only behavior:** the race half of BUG-2631 (two concurrent transactions).

**Model facts (table `purchase_orders`, `app.models.purchase_order.PurchaseOrder`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` CASCADE | — |
| `po_number` | String(100) NOT NULL; UNIQUE `(workspace_id, po_number)` (`uq_po_workspace_number`); plain index on `po_number` | — |
| `account_id` | Integer nullable, FK `accounts.id` RESTRICT | `NULL` |
| `destination_type` | String(50) NOT NULL (`storage` / `machine` / `project`, not enforced) | — |
| `destination_id` | Integer NOT NULL, no FK (factory / machine / project component id) | — |
| `order_date`, `expected_delivery_date`, `actual_delivery_date` | Date nullable | `NULL` |
| `subtotal`, `total_amount` | Numeric(15, 2) NOT NULL | Python `0` |
| `current_status_id` | Integer NOT NULL, FK `statuses.id` RESTRICT | — |
| `order_workflow_id` | nullable FK `order_workflows.id` | `NULL` |
| `required_approvals` | Integer nullable | `NULL` |
| `invoice_id` | nullable FK `account_invoices.id` SET NULL, indexed, **not unique** | `NULL` |
| `supplier_confirmed`, `details_confirmed`, `items_confirmed`, `invoice_confirmed` | Boolean NOT NULL | Python `False` |
| `invoice_ever_linked`, `paid`, `voided` | Boolean NOT NULL | `false` (Python and database) |
| `void_note`, `voided_at`, `voided_by` | nullable | `NULL` |
| `created_by` | Integer NOT NULL, FK `profiles.id` SET NULL | — |
| `created_at` | DateTime (naive UTC) NOT NULL | Python `utcnow` |
| `updated_by`, `updated_at` (`onupdate=utcnow`), `items_updated_at` | nullable | `NULL` |

Table `purchase_order_items`: `workspace_id` NOT NULL; `purchase_order_id` NOT NULL FK CASCADE; `line_number` Integer NOT NULL, **not unique**; `item_id` NOT NULL FK `items.id` RESTRICT; `quantity_ordered` Numeric(15, 2) NOT NULL; `quantity_received` NOT NULL (Python default 0); `quantity_returned`, `quantity_refunded` NOT NULL default `0`; `unit_price`, `line_subtotal` nullable; `notes`. Relationship `item` is `lazy="joined"`.

Stage statuses are workspace rows named `Draft`, `Planning`, `Receiving`, `Complete` (`app/db/seed_po_workflow.py`).

**Notes for the test designer:**
- `from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao` (singletons of `PurchaseOrderDAO` / `PurchaseOrderItemDAO`). Models: `app.models.purchase_order.PurchaseOrder`, `app.models.purchase_order_item.PurchaseOrderItem` (G1). PO relationships: `current_status` (the status the hub, `list_for_destination` and `get_by_id_and_workspace` load — check `"current_status" not in sqlalchemy.inspect(po).unloaded` before reading it), `account`, `workflow`, `invoice`, `creator`, `updater`, `approvers`; line relationships `purchase_order` (backref `line_items`) and `item` (G2).
- Statuses and types are plain strings, there is no enum to import: invoice `invoice_status` `draft` / `confirmed` / `locked` / `voided`, `payment_status` `unpaid` / `partial` / `paid` / `overdue`, `invoice_type` `payable` / `receivable`; PO `destination_type` `storage` / `machine` / `project`.
- **What real writes look like (G4–G6).** A real **PO void** (`PurchaseOrderService.void_purchase_order`) reverses received stock, voids a confirmed invoice or deletes a draft one, unlinks it (`invoice_id = None`, `invoice_confirmed = False`, `paid = False`) and sets `voided = True`, `void_note`, `voided_at`, `voided_by` (`updated_at` by `onupdate`; `current_status_id` unchanged). A real **invoice void** (only from `confirmed`) sets `invoice_status = 'voided'`, `void_note`, `paid_amount = 0.00`, `payment_status = 'unpaid'` and voids its payments. A **machine soft delete** sets `is_deleted = True`, `is_active = False`, `deleted_at`, `deleted_by`. A **project component delete** removes the row. A card that builds a voided PO still linked to an invoice, or a voided invoice whose `payment_status` is not `unpaid`, uses legacy or invalid data; that is fine for a filter check, but the card should say so. Parents: `make_workspace`, `make_profile` (`tests/unit/factories.py`); `Status(workspace_id, name, comment)`; `Account(workspace_id, name)` (`is_deleted` for BUG-2634); `Factory(workspace_id, name, abbreviation)`; `Machine(workspace_id, name, factory_id)`; `Project` + `ProjectComponent` for the factory filter; `AccountInvoice(workspace_id, account_id, invoice_type='payable', invoice_amount, invoice_date, invoice_status, payment_status)`; `Item(workspace_id, name, name_normalized, unit)`.
- Set `created_at` / `updated_at` explicitly (or with SQL `UPDATE`) for ordering cards: `updated_at` has `onupdate`, so any ORM update of the row stamps it.
- Empty aggregates come back as `Decimal('0')`, not `Decimal('0.00')`; compare numerically.
- Hub callables accept the filter keywords of `_apply_purchase_order_hub_filters` only; any other keyword raises `TypeError`.
- BUG-2637: two POs on one invoice; force a sequential scan (`SET LOCAL enable_indexscan/enable_bitmapscan/enable_indexonlyscan = off`), update the lower `id`, flush, `expire_all()` → **non-strict** xfail, or a strict check that the SQL ends in `ORDER BY purchase_orders.id`. Same approach for BUG-2636 / BUG-2638 ties.

## Not specified
- `PurchaseOrderDAO.get_by_workspace` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-10); Q1).
- `PurchaseOrderDAO.get_next_number` — dead code, to be removed (same; Q1).
- `_hub_base_query` — builds the hub query: `_apply_purchase_order_hub_filters` on all POs with the status eagerly loaded; no logic of its own (its effect is in each hub callable's rules).
- `purchase_order_dao`, `purchase_order_item_dao` — module-level singletons.
- Inherited `BaseDAO` methods — base spec.

---

## `_purchase_order_is_fully_closed_clause()`
**Shape:** helper
**Persistence:** pure (SQL expression)
**Visibility:** internal (used by: `_apply_purchase_order_hub_filters`, `aggregate_hub_stats`)

**Purpose:** The SQL condition "this PO is fully closed".

**Rules:**
- **R1.** A PO is fully closed when its current status's name is exactly `Complete` **and** `paid` is true. A `Complete` unpaid PO, a paid PO in any other stage, and a status named `complete` / `Complete ` are not fully closed (exact spelling: BUG-1881, owner OQ-13 — fixed there, not here).
- **R2.** It needs the status table joined; the callers join it (see their rules).

**Errors:** none. **Side effects:** none.

---

## `_apply_purchase_order_hub_filters(query, *, workspace_id, account_id=None, invoice_id=None, date_from=None, date_to=None, status_ids=None, factory_id=None, destination_type=None, invoice_filter=None, search=None, exclude_complete=True, exclude_voided=True)`
**Shape:** helper (filter)
**Persistence:** reads
**Visibility:** internal (used by every hub callable through `_hub_base_query`)

**Purpose:** The hub's filters, shared by list, count, stats, recent and highlights.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| workspace_id | int | always applied |
| account_id, invoice_id, factory_id | int / None | `None` = no filter; `0` is a filter (matches nothing) |
| date_from, date_to | date / None | inclusive calendar days of `created_at` |
| status_ids | list[int] / None | empty list = no filter |
| destination_type | str / None | `""` = no filter; any other string compared exactly |
| invoice_filter | str / None | `invoiced`, `not_invoiced`, `outstanding_payment`; anything else = no filter (the service turns `all` into `None`) |
| search | str / None | trimmed; blank = no filter |
| exclude_complete, exclude_voided | bool | default **True** here; the service and the endpoint pass `False` unless asked, the web app sends `true` unless "show complete" / "show voided" is on |

**Rules:**
- **R1.** Only POs of `workspace_id` are kept; another workspace's PO never appears, whatever the other filters.
- **R2.** `account_id` given → only POs with that supplier; `invoice_id` given → only POs linked to that invoice. `None` → no filter. `0` → no PO matches.
- **R3.** `date_from` keeps POs created at or after 00:00:00 of that day; `date_to` keeps POs created at or before 23:59:59.999999 of that day (the whole end day counts). Days are UTC days (`created_at` is naive UTC; decided intended under the delegation, 2026-11-10: the system has no workspace time zone here). `date_from` after `date_to` → nothing, no error.
- **R4.** `status_ids` non-empty → only POs whose current status id is in the list; `None` or `[]` → no filter.
- **R5.** `destination_type` non-empty → only POs with exactly that destination type (case-sensitive); `None` / `""` → no filter.
- **R6.** `factory_id` given → POs for that factory: destination `storage` with `destination_id = factory_id`; destination `machine` whose machine (of this workspace) has that factory; destination `project` whose project component (of this workspace) belongs to a project of that factory. A soft-deleted machine still counts (a machine soft delete writes `is_deleted = True`, `is_active = False`, `deleted_at`, `deleted_by`; G4). Project components have **no** soft delete: deleting one removes the row (`ProjectComponentService.delete_component` → `remove`), and `destination_id` has no foreign key, so the PO stays but no longer matches the factory through that component. A soft-deleted project (`is_deleted`, `deleted_at`, `deleted_by`) still places its components' POs under its factory — described, not asked (projects deferred, revisit after launch, owner 2026-11-10). A factory id with no such PO → nothing.
- **R7.** `invoice_filter='invoiced'` → only POs with an invoice; `'not_invoiced'` → only POs without one.
- **R8.** Any other `invoice_filter` value (e.g. `bogus`, `all`, `""`) → no invoice filter (verified; per the expense manager spec's R6, intended).
- **R9.** [BUG-2640] `invoice_filter='outstanding_payment'` → only POs with an invoice whose `invoice_status` is `confirmed` or `locked` and whose `payment_status` is not `paid` (`unpaid`, `partial`, `overdue`). A PO whose invoice is `draft` or `voided` is not kept; a PO with no invoice is not kept. *(Today: any `invoice_status` counts — a draft and a voided invoice were both kept, verified.)*
- **R10.** `exclude_voided=True` → voided POs are left out; `False` → kept. `exclude_complete=True` → fully closed POs (`_purchase_order_is_fully_closed_clause` R1) are left out; `False` → kept.
- **R11.** [BUG-2633] (HR-8) `search` (trimmed; blank or whitespace-only = no filter) keeps POs whose `po_number` or supplier name contains the text, case-insensitively; `%`, `_` and `\` in the text match literally. *(Today: unescaped — `_` or `%` alone matches every PO, verified; `\` escapes the next character.)* A PO with no supplier is matched by its number only.
- **R12.** [BUG-2634] (HR-4) A soft-deleted supplier's name does not match; such a PO is still found by its number. *(Today: the deleted account's name matches.)*
- **R13.** The filters combine with AND; joins add no duplicate rows (a PO links to at most one invoice, one status and one account).
- **R14.** An unknown keyword raises `TypeError`.

**Errors:** none of its own. **Side effects:** none.

---

## `PurchaseOrderDAO.list_for_hub(db, *, workspace_id, skip=0, limit=50, **filters)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.list_purchase_orders_for_hub` ← `GET /purchase-orders/`)

**Purpose:** One page of the PO hub list.

**Returns:** list of `PurchaseOrder`, current status loaded.

**Rules:**
- **R1.** Returns the POs matching the filters (`_apply_purchase_order_hub_filters` R1–R14), with the DAO's defaults `exclude_complete=True`, `exclude_voided=True` when not passed.
- **R2.** Ordered by `created_at` descending, then `id` descending (newest first, stable).
- **R3.** `skip` / `limit` apply after all filters; defaults 0 and 50. A page is short only at the end.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.count_for_hub(db, *, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.count_purchase_orders_for_hub` ← `GET /purchase-orders/` `total`)

**Rules:**
- **R1.** Returns, as `int`, the number of distinct POs matching the same filters as `list_for_hub` (same defaults); always equals the length of the unpaged list. No match → `0`.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.list_recent_for_hub(db, *, workspace_id, limit=10, **filters)`
**Shape:** list (top-N)
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.list_purchase_orders_recent_for_hub` ← `GET /purchase-orders/stats/` `recent_orders`, limit 10)

**Rules:**
- **R1.** [BUG-2635] The `limit` (default 10) matching POs with the latest activity: ordered by `coalesce(updated_at, created_at)` descending, then `id` descending. *(Today: `updated_at` desc, then `created_at` desc, no `id`; never-edited POs (`updated_at` empty) come **before** every edited one — verified the only edited PO came last.)*
- **R2.** Same filters and defaults as `list_for_hub` R1.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.get_pending_highlights_for_hub(db, *, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.purchase_order_pending_highlights_for_hub` ← `GET /purchase-orders/stats/`)

**Purpose:** The hub's "needs attention" panel.

**Returns:** dict with keys `pending_planning_count` (int), `pending_planning` (list), `missing_invoice_count` (int), `missing_invoice` (list), `oldest_drafts` (list). Each list entry is `{"id", "order_number" (= po_number), "status_name", "created_at"}`.

**Rules:**
- **R1.** All five parts cover only POs matching the filters (same defaults as `list_for_hub`). `exclude_complete=True` together with the status join works (verified; no error).
- **R2.** [BUG-2635] `pending_planning_count` = number of matching POs in a status named exactly `Planning` (BUG-1881); `pending_planning` = at most 3 of them, latest activity first (`coalesce(updated_at, created_at)` desc, then `id` desc). *(Today: `updated_at` desc only — never-edited POs first, ties unordered.)*
- **R3.** [BUG-2635] `missing_invoice_count` = number of those Planning POs that have a supplier and no invoice; `missing_invoice` = at most 3 of them, same order as R2. *(Today: as R2.)* A Planning PO with no supplier is not "missing an invoice".
- **R4.** `oldest_drafts` = at most 5 matching POs in a status named exactly `Draft`, oldest `created_at` first.
- **R5.** [BUG-2636] (HR-6) Ties on `created_at` in `oldest_drafts` are broken by `id` ascending. *(Today: unordered.)*
- **R6.** `status_name` is the status's name (always present: the status is required).
- **R7.** No matching PO → counts `0`, lists empty.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.aggregate_hub_stats(db, *, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.purchase_order_hub_stats` ← `GET /purchase-orders/stats/`)

**Returns:** tuple `(total_count: int, total_value: Decimal, open_count: int, open_value: Decimal, not_invoiced_count: int)`.

**Rules:**
- **R1.** Covers exactly the POs matching the filters (same defaults as `list_for_hub`), each counted once. `total_count` = their number.
- **R2.** [BUG-2639] `total_value` = sum of `total_amount` of the matching POs that are **not voided**; a voided PO kept by `exclude_voided=False` adds nothing. *(Today: voided POs are added — verified 1006.00 with a voided 400.00; intended 606.00.)*
- **R3.** `open_count` / `open_value` = count / sum of the **full** `total_amount` of the non-voided POs that are not fully closed (`_purchase_order_is_fully_closed_clause` R1): a Complete unpaid PO counts with its full total, as does a paid PO still in `Receiving` ✅ (OQ-36, intended).
- **R3a.** [BUG-2639] A voided PO is never open: it adds nothing to `open_count` or `open_value`. *(Today: a voided PO counts as open — verified `5` / `906.00` for the example in OQ-35; intended `4` / `506.00`.)*
- **R3b.** A voided PO still counts in `total_count` (R1) and, when it has no invoice, in `not_invoiced_count` (R4). A real PO void unlinks its invoice (G6), so a voided PO normally counts as not invoiced.
- **R4.** `not_invoiced_count` = number of those with no invoice.
- **R5.** No matching PO → `(0, Decimal('0'), 0, Decimal('0'), 0)`.
- **R6.** Sums are exact sums of 2-decimal amounts (no rounding step).

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.list_for_destination(db, *, workspace_id, destination_type, destination_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.get_incoming_summary_for_factory`, `PurchaseOrderService` (incoming for a machine / factory / component))

**Rules:**
- **R1.** Returns every PO of the workspace with exactly that destination type and id, current status loaded — any status, voided included (callers decide; BUG-717 is the inventory manager's).
- **R2.** Newest `created_at` first; not paged, ties in any order.
- **R3.** Another workspace's PO with the same destination is never returned; no match → `[]`.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (manager, service, `AttachmentManager`)

**Rules:**
- **R1.** Returns the PO with that id in that workspace, current status loaded; voided POs are returned.
- **R2.** `None` for an unknown id or a PO of another workspace.
- **R3.** No row lock (FU-1).

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.get_by_invoice_id(db, *, invoice_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.get_po_by_invoice_id`)

**Rules:**
- **R1.** Returns the PO of this workspace linked to that invoice.
- **R2.** `None` when no PO of this workspace has it (verified for another workspace's PO on the same invoice id).
- **R3.** [BUG-2637] (HR-6) With two or more POs of the workspace on that invoice, the lowest `id` is returned. *(Today: no `ORDER BY`.)*
- **R4.** `invoice_id=None` is compared as `IS NULL` (returns some PO without an invoice); no caller passes it.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderDAO.allocate_po_number(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.create_purchase_order` ← `POST /purchase-orders/`)

**Returns:** a string `PO-<year>-<n>`, `<n>` zero-padded to at least 3 digits.

**Rules:**
- **R1.** [BUG-2632] `<year>` is the current UTC year (`utcnow().year`). *(Today: `datetime.now().year`, the server's local year; verified `PO-2031-001` with a patched clock.)*
- **R2.** `<n>` = the highest numeric suffix among this workspace's numbers starting with `PO-<year>-`, plus 1: none → `001`; after `PO-2026-007` → `008`; after `PO-2026-9999` → `10000`. Other years' numbers do not count.
- **R3.** The suffix is the text after the last `-`; a suffix that is not an integer (`PO-2026-abc`) is ignored; `PO-2026-1-2` counts as 2. The prefix match is case-sensitive (`po-2026-…` is not counted; numbers are system-made and not editable through `PurchaseOrderUpdate`).
- **R4.** The number is returned, not stored; the manager inserts the row.
- **R5.** [BUG-2630] Only this workspace's numbers matter: another workspace holding `PO-2026-001` does not change this workspace's first number (`PO-2026-001`). *(Today: every candidate already used by **any** workspace is skipped; verified `PO-2026-002`.)*
- **R6.** If 1000 consecutive candidates are all taken, raises `HTTPException` 500 "Could not allocate a unique purchase order number". *(Today reachable only through other workspaces' numbers; after BUG-2630 only through a race.)* **Decided 2026-11-11 (G3, by Claude under the reviewer's delegation):** while BUG-2630 is open the cards reach R6 through other workspaces' numbers (today's path). With the fix, R6 is reachable only by a race, which one session cannot stage, so the fix keeps the "is this number taken in this workspace" check in a named module-level helper `_po_number_taken(db, *, workspace_id, po_number)` (*requires new helper*) and the cards patch it to always answer taken. If BUG-2631's fix replaces the loop with a counter, R6, its Errors row and its cards go with the loop. Reason: a deterministic single-session test of a defensive branch.
- **R7.** [BUG-2631] Two creates at once in one workspace get distinct numbers and both succeed. *(Today: read with no lock or counter; the second insert fails on `uq_po_workspace_number` with `IntegrityError` 23505 — verified for a duplicate in one workspace; the same number in another workspace is accepted. Integration-only.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| 1000 candidates taken | `HTTPException` 500 | `Could not allocate a unique purchase order number` |

**Side effects:** none (reads only).

---

## `PurchaseOrderItemDAO.get_by_order(db, *, purchase_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (manager, service, return manager)

**Rules:**
- **R1.** Every line of that PO whose own `workspace_id` matches, by `line_number` ascending (not paged; lines sharing a number come in any order — FU-3).
- **R2.** Another workspace's id or an unknown PO → `[]`.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderItemDAO.get_by_purchase_order_ids(db, *, workspace_id, purchase_order_ids)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.get_incoming_summary_for_factory`)

**Rules:**
- **R1.** Empty list → `[]` with no query.
- **R2.** Every line of the given POs in this workspace, ordered by PO id, then `line_number`; ids of another workspace's POs contribute nothing.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (manager, return manager)

**Rules:**
- **R1.** The line with that id in that workspace, or `None` (unknown id, another workspace's line). No lock.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderItemDAO.summarize_by_purchase_order_ids(db, *, workspace_id, purchase_order_ids)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderService._attach_item_summaries` ← hub list)

**Returns:** `{po_id: {"item_count": int, "quantity_ordered_total": Decimal, "quantity_received_total": Decimal, "quantity_refunded_total": Decimal}}` — the last key from BUG-2641 (*today missing*).

**Rules:**
- **R1.** Empty list → `{}`. A PO with no lines (or another workspace's PO) has no key.
- **R2.** `item_count` = number of lines; `quantity_ordered_total` = sum of `quantity_ordered`; `quantity_received_total` = sum of `quantity_received`; returned quantities play no part, and different items' units are added together. Verified 3 lines → `3`, `16.50`, `8.00` ✅ (OQ-38: ordered and received stay the raw sums).
- **R2a.** [BUG-2641] Each summary also has `quantity_refunded_total` = sum of `quantity_refunded` over the order's lines (`Decimal`; `0` when nothing was refunded). Example: lines 10 / 7 / 3, 5.5 / 0 / 0 and 1 / 1 / 0 (ordered / received / refunded) → `16.50`, `8.00`, `3.00`. *(Today: no such key.)* The wording and the "done" test are not this DAO's (FU-5).

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderItemDAO.preview_names_by_purchase_order_ids(db, *, workspace_id, purchase_order_ids, limit=4)`
**Shape:** compute (top-N per order)
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderService._attach_item_summaries`)

**Rules:**
- **R1.** Empty list, or `limit` 0 or negative → `{}`.
- **R2.** For each PO of this workspace with lines: up to `limit` (default 4) names, one per line (the same item twice gives its name twice). A line whose item name is empty gives `Item #<item_id>`. POs with no lines have no key.
- **R3.** [BUG-2638] (HR-6) Names are taken in `line_number` order, then line `id` ascending. *(Today: no `id` tie-breaker.)*

**Errors:** none. **Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 29 | `Complete` and `paid` | `_purchase_order_is_fully_closed_clause` R1 |
| 48 | workspace filter | `_apply…` R1 |
| 50–53 | `account_id` / `invoice_id` `is not None` | `_apply…` R2 |
| 54–57 | `date_from` / `date_to` given; `time.min` / `time.max` | `_apply…` R3 |
| 58 | `status_ids` truthy | `_apply…` R4 |
| 60 | `destination_type` truthy | `_apply…` R5 |
| 63–92 | `factory_id` given; three destination branches | `_apply…` R6 |
| 94–97 | `invoiced` / `not_invoiced` | `_apply…` R7 |
| 98–105 | `outstanding_payment` | `_apply…` R9 |
| 94–105 | any other value | `_apply…` R8 |
| 107 | `exclude_voided` | `_apply…` R10 |
| 110–113 | `exclude_complete` (status join) | `_apply…` R10, `_purchase_order_is_fully_closed_clause` R2 |
| 115–122 | `search` truthy and non-blank; `ILIKE` unescaped; account outer join | `_apply…` R11, R12 |
| 32–47 | keyword-only filters | `_apply…` R14 |
| 168–174 | order, offset, limit | `list_for_hub` R2, R3 |
| 177–183 | distinct count; `or 0` | `count_for_hub` R1 |
| 193–198 | recent order, limit | `list_recent_for_hub` R1 |
| 205 | extra status join | `get_pending_highlights_for_hub` R1 |
| 208–212 | Planning count and sample | `get_pending_highlights_for_hub` R2 |
| 214–221 | missing invoice (no invoice, has supplier) | `get_pending_highlights_for_hub` R3 |
| 223–228 | Draft sample | `get_pending_highlights_for_hub` R4, R5 |
| 235 | `status.name if status else None` | `get_pending_highlights_for_hub` R6 |
| 262–278 | count / sum / open case / not invoiced case | `aggregate_hub_stats` R1–R4 |
| 280–286 | `or 0` conversions | `aggregate_hub_stats` R5, R6 |
| 296–306 | destination match, order | `list_for_destination` R1–R3 |
| 309–314 | id + workspace | `get_by_id_and_workspace` R1, R2 |
| 319–326 | invoice + workspace, `.first()` | `get_by_invoice_id` R1–R4 |
| 339 | `datetime.now().year` | `allocate_po_number` R1 |
| 342–349 | this workspace's numbers with the prefix | `allocate_po_number` R2, R3 |
| 351–355 | parse suffix; `ValueError` → skip | `allocate_po_number` R3 |
| 357 | `max_seq + 1 if max_seq else 1` (same result either way) | `allocate_po_number` R2 |
| 358–367 | candidate loop; global "taken" check | `allocate_po_number` R5, R7 |
| 369–372 | loop exhausted | `allocate_po_number` R6 |
| 377 | order lines by `line_number` | `get_by_order` R1, R2 |
| 386–387 | empty ids | `get_by_purchase_order_ids` R1 |
| 388–396 | lines of the ids, ordered | `get_by_purchase_order_ids` R2 |
| 399 | id + workspace | `PurchaseOrderItemDAO.get_by_id_and_workspace` R1 |
| 408–409 | empty ids | `summarize_by_purchase_order_ids` R1 |
| 410–431 | grouped sums | `summarize_by_purchase_order_ids` R1, R2 |
| 441–442 | empty ids or `limit <= 0` | `preview_names_by_purchase_order_ids` R1 |
| 443–456 | rows ordered by PO, `line_number` | `preview_names_by_purchase_order_ids` R3 |
| 459–462 | bucket full → skip; empty name → `Item #id` | `preview_names_by_purchase_order_ids` R2 |

## Gap log
G1 (purchase_order.cases.md gap 1) — Fact — `PurchaseOrderItem` lives in `app.models.purchase_order_item`; added to Notes for the test designer.
G2 (gap 2) — Fact — the status relationship is `PurchaseOrder.current_status`; added to Notes with the other relationship names and a `loaded` check.
G3 (gap 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-11) — after BUG-2630, R6 is reachable only by a race; the fix keeps a named helper `_po_number_taken` that the cards patch, or R6 goes with the loop under BUG-2631. Written into `allocate_po_number` R6. Reason: a deterministic single-session test of a defensive branch.
G4 (gap 4) — Fact / Contradiction — project components have no soft delete (the row is removed), so "deleted components still count" was wrong; `_apply…` R6 rewritten (machine soft-delete columns named; soft-deleted projects still count, projects deferred). PUO-HF-24 must be redesigned.
G5 (gap 5) — Fact — a real invoice void writes `invoice_status 'voided'`, `void_note`, `paid_amount 0.00`, `payment_status 'unpaid'`; OQ-37 Background corrected; Notes list it.
G6 (gap 6) — Fact — a real PO void also unlinks the invoice (`invoice_id None`, `invoice_confirmed False`, `paid False`), reverses stock and voids or deletes the invoice; Notes list it; `aggregate_hub_stats` R3b.
