# Spec — `app/dao/account_invoice.py`

> **Status:** APPROVED (2026-11-11; OQ-41 answered by the owner → BUG-2692; both case-designer gaps closed, Gap log at the end)
> **Source commit:** e48a092

> **Review round 2026-11-10 (describe).** **Delegated:** both house-rule lines (HR-16, HR-4) and Q1 (dead `get_by_order`) decided by Claude under the reviewer's delegation (2026-11-10). None of them is the owner's own answer. **Owner:** OQ-41 (what the account summary's totals mean when payables and receivables are mixed) is parked in `docs/testing/owner-questions.md`, not blocking.

> **Review round 2026-11-11 (apply-review + fill-gaps).** **Owner:** OQ-41 — suggested answer: the summary returns payable and receivable figures separately, as in OQ-30/31 (owner, 2026-11-11) → 🐞 BUG-2692, `summarize_invoices` R5. **Delegated (decided by Claude under the reviewer's delegation, 2026-11-11):** the exact return shape of the split summary (R5; the owner decided *what* is split, the tuple layout is mechanics); after BUG-635 "today" reaches this DAO as a `today` parameter (G1); HR-16 cards that build an invoice of workspace 1 on another workspace's account stay as read checks that the invalid row must not leak (Notes). **Gaps:** both gaps of `account_invoice.cases.md` closed (Gap log at the end).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated (`get_by_id_and_workspace`, `create`, `update`, `remove` are inherited and used by `AccountInvoiceManager`, `InvoicePaymentManager`, the order managers/services and `AttachmentManager`).
>
> **Already decided in the approved manager spec** (`tests/unit/managers/account_invoice_manager.spec.md`) and reused here with their IDs, not re-asked: HR-8 escaping of `account_name_search` / hub `search` and the ASCII-only id shortcut (BUG-622), case-insensitive hub order (BUG-623), drafts left out of every open-balance and money view (BUG-634), overdue derived at query time (BUG-635), inactive accounts with an open balance shown on the hub (BUG-636), whitespace-only invoice-number search = no filter (BUG-637). The manager spec states these as rules of the manager methods that forward here; **this spec is where the DAO lines live**, and the two must say the same thing. More than two decimals on a payment: BUG-604 (fix in the payment schema).
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order counts as deterministic unless it ends in `id`. HR-15: money rounds half away from zero (Postgres `Numeric(15, 2)` does this on store; this DAO does no Python rounding). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (my own throwaway script `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdao\account_invoice\`, one transaction on `marker_test`, rolled back, foreign keys off with `session_replication_role = replica` for the work-order row only, private `COVERAGE_FILE`; nothing committed): `summarize_invoices` on an account with a 1,000.00 payable and a 200.00 receivable → `(2, 1200.00, 0.00, 1200.00)`; empty results `(0, Decimal('0'), Decimal('0'), Decimal('0'))` and `(0, Decimal('0'), 0, 0)`; an invoice of workspace A on workspace B's account is listed, matched by B's account name and counted in A's hub KPIs, but absent from A's hub page; a soft-deleted work order's number still finds its invoice; `"   "` search → 0 rows; `"²"` → `ValueError`; `update_paid_amount` not found / other workspace → `None`, `999.995` → status `partial` with stored `1000.00`, `-100` on a paid invoice → `paid_amount 0.00`, status still `paid`, a voided invoice → `partial`, no `FOR UPDATE` in its SQL; `get_by_order` returns a purchase-order and an expense-order invoice with the same `order_id`; hub SQL `ORDER BY accounts.name ASC, accounts.id ASC`. **Read, not run:** `AccountInvoiceManager`, `InvoicePaymentManager.create_payment`, `AccountInvoiceService`, `AccountService.get_accounts_hub_page`, endpoints `GET /invoices/`, `GET /invoices/hub-summary/`, `GET /accounts/hub/`, `GET /accounts/{id}/invoice-summary/`, `/open-invoices/`, `/invoices/`; web app `AccountOverviewPanel.tsx`, `useAccountInvoiceTotals.ts`, `accountsApi.ts`. **Not run:** HTTP; two concurrent transactions.

## Review
> Delegated items decided 2026-11-10; one owner question parked (not blocking).

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-16 | An invoice whose account belongs to another workspace is listed, found by that account's name and counted in totals | bug — BUG-2690 | Claude, delegated |
| HR-4 | A deleted work order's number still finds its invoice in the search | bug — BUG-2691 | Claude, delegated |
| Q1 | "Invoices of an order" has no caller and mixes order types | remove | Claude, delegated |
| OQ-41 | The account invoice summary adds what we owe and what we are owed into one total | bug — split payable / receivable (BUG-2692) | owner, 2026-11-11 |

### House-rule violations — applied automatically

- **HR-16** `_build_filtered_query` R2a (every list, summary and KPI that uses it) — the account is joined by id only. An invoice of this workspace whose `account_id` names another workspace's account is listed with that account's id, matched by `account_name_search` on that account's name, and counted in `summarize_invoices`, `summarize_open_hub_type` and `count_accounts_with_any_open_balance` (verified: A's payable KPI said 2 open, 1,050.00, 2 accounts, while A's hub page showed one account with 1,000.00). Intended, per BUG-1086 / BUG-1801: such an invoice is treated as not found — left out of every list, count and total, in the query, before paging, by also requiring the account's `workspace_id` to equal the invoice's. The row stays for a one-off clean-up (`scripts/find_cross_workspace_rows.py`).
**Answer:** bug — per HR-16 (house rule)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2690 (pattern `cross-workspace-row-exposed`). `_open_balance_subquery` gets the same join condition; on the hub page itself the outer account list is already this workspace's, so there it changes nothing observable. Rules: `_build_filtered_query` R2a, `_open_balance_subquery` R1a.

- **HR-4** `_order_number_search_conditions` R4 — the order-number search reads `work_orders` without looking at `is_deleted`: a soft-deleted work order's number (forward link `order_type = 'work_order'` + `order_id`, or reverse link `work_orders.invoice_id`) still matches. Verified: deleted `WO-DEL-77` linked to invoice 1 → searching `wo-del-7` returns invoice 1. Intended: a soft-deleted work order neither matches nor filters (HR-4, related rows); the invoice itself stays visible and is still found by its own numbers. Purchase, expense and sales orders have no soft-delete column; a **voided** purchase/expense order is a state, not a deletion, and its number keeps matching (intended — a voided order's invoice is still a real record).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2691 (pattern `join-ignores-soft-deleted`). Rules: `_order_number_search_conditions` R4.

Checked and **not** a new line here: **HR-5** — every filter is in the query before `offset`/`limit`; `total` counts are taken after filters. **HR-6** — `list_invoices` and both paged lists end in `id`; the hub order is BUG-623. **HR-7** — the endpoints set `ge=1` on every `limit`. **HR-8** — `invoice_number_search` and order numbers are escaped; `account_name_search` / hub `search` and the digit shortcut are BUG-622. **HR-9** — this DAO writes no audit stamp. **HR-10** — `update_paid_amount` is a read-then-change of money without its own lock, but its only caller (`InvoicePaymentManager.create_payment` R2) already holds `SELECT … FOR UPDATE` on the same row in the same transaction, and the DAO's read returns that same locked row from the session; decided by Claude under the reviewer's delegation (2026-11-10): intended, the lock is the caller's precondition (stated in `update_paid_amount` R7). **HR-15** — sums are of `Numeric(15, 2)` columns (exact); the one value that can carry more than 2 decimals is a payment amount, BUG-604. **HR-4** for accounts — soft-deleted accounts are already left out (`_build_filtered_query` R2); inactive accounts are BUG-636.

### Precedent matches

None beyond the reused manager-spec bugs listed at the top.

### New questions

### Q1. "Invoices of an order" has no caller — 🗑️ removed
**Background:** `get_by_order(order_id, workspace_id)` returns every invoice of the workspace whose `order_id` equals the id. Invoices link to orders polymorphically (`order_type` + `order_id`, no foreign key), so ids of different order kinds overlap.
**What happens today:** nothing in `app/`, `tests/` or `scripts/` calls it (the order code finds invoices through the order's own `invoice_id`). It ignores `order_type`: verified, with a purchase order and an expense order both id 4242, it returns both orders' invoices. No `ORDER BY`.
**Example:** deleting it changes no API response.
**Rules affected:** none (moved to Not specified)
**Answer:** remove — per the sales order DAO precedent (`get_by_factory`): no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): goes under **Not specified** as dead code and into `docs/testing/dead-code-removal-checklist.md`. No bug ID.

### OQ-41. The account invoice summary adds what we owe and what we are owed into one total — 🐞 BUG-2692
**Background:** an account can have both kinds of invoice: **payable** (we owe them — purchase orders, expenses) and **receivable** (they owe us — sales, and the credit note a purchase return creates against the same supplier). The account page's KPI strip ("Invoiced / Paid / Outstanding") calls `GET /accounts/{id}/invoice-summary/` **without** a type filter.
**What happens today:** with no `invoice_type`, `invoiced_total`, `paid_total` and `outstanding_total` are plain sums over both kinds.
**Example:** supplier Acme has a 1,000.00 unpaid bill and a 200.00 credit note from a returned delivery. The account page shows Invoiced 1,200.00, Outstanding 1,200.00 (verified) — although we owe Acme 1,000.00 and they owe us 200.00 (net 800.00 payable).
**Rules affected:** `summarize_invoices` R5
**Suggested answer:** bug — same root as OQ-30/31 (owner: split, don't add different money flows): the summary returns payable and receivable figures separately (`payable_invoiced/paid/outstanding`, `receivable_invoiced/paid/outstanding`); the combined fields go, or stay only when an `invoice_type` filter is given. A net figure is the web app's to show, if wanted.
**Alternatives:** (a) intended — "invoiced" is volume across both kinds. (b) keep one set of fields but net them (receivable minus payable, signed).
**Answer:** owner, 2026-11-11: suggested answer (payable and receivable figures shown separately, as in OQ-30/31). → BUG-2692
**Resolution:** 🐞 BUG-2692 (pattern `report-total-mixes-money-in-and-out`, as BUG-2481). The DAO returns the count plus one set of totals per invoice type; the combined money fields go. Return shape decided by Claude under the reviewer's delegation (2026-11-11): one fixed shape whether or not `invoice_type` is given (the type not asked for sums to 0), so callers never branch on it. The response model and KPI strip are FU-2. Rules: `summarize_invoices` R5 (tagged).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Account invoice manager spec** (`tests/unit/managers/account_invoice_manager.spec.md`, APPROVED) | Its shared filter rules R1–R2 and `get_invoices_hub_summary` R1 should name BUG-2690 (an invoice on another workspace's account is left out). Wording only; the manager cases need one HR-16 card if the designer wants it there too. | HR-16 line |
| FU-2 | **Account invoice manager / service / endpoint / web app** (`app/managers/account_invoice_manager.py` `summarize_invoices`, `app/services/account_invoice_service.py`, `app/api/v1/endpoints/accounts.py` line 165, `app/schemas/account_invoice.py` `AccountInvoiceSummaryResponse`, web `useAccountInvoiceTotals.ts` / `AccountOverviewPanel.tsx`) | OQ-41 answered "split" (owner, 2026-11-11; BUG-2692): the endpoint unpacks four values today and must take the new shape; `AccountInvoiceSummaryResponse` replaces `invoiced_total` / `paid_total` / `outstanding_total` with `payable_invoiced_total`, `payable_paid_total`, `payable_outstanding_total`, `receivable_invoiced_total`, `receivable_paid_total`, `receivable_outstanding_total` (`invoice_count` stays); the KPI strip shows the two sets (a net figure, if wanted, is computed in the web app). Same bug ID, fixed together with the DAO. | OQ-41 |

## Overview
`AccountInvoiceDAO` is the read side of account invoices (payables and receivables): the filtered invoice list used by `GET /invoices/` and the account pages, the paged open-invoice list, the account summary totals, the workspace hub KPIs and the per-account hub rollups; plus `update_paid_amount`, which adds a recorded payment to an invoice. Callers: `AccountInvoiceManager` (every list/summary method forwards here unchanged), `InvoicePaymentManager.create_payment` (`update_paid_amount`), and through the inherited `BaseDAO` methods most order managers/services. Invariants it is meant to protect: workspace isolation, invoices of soft-deleted accounts never shown, voided invoices kept out of money totals and open balances. It never commits; only `update_paid_amount` flushes.

**Callables:** 14 specified · 1 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** none. After BUG-635 the overdue rules need "today": it reaches this DAO as a keyword parameter `today: date` (the manager passes `utcnow().date()`, read in the manager and patched at `app.managers.account_invoice_manager.utcnow`, manager spec G3). The DAO reads no clock and never uses `CURRENT_DATE`, so DAO tests pass a fixed `today` and patch nothing. *(requires new parameter `today` on `_build_filtered_query`, `list_invoices`, `list_invoices_page`, `list_invoices_page_filtered`, `summarize_invoices`, `_open_balance_subquery`, `list_accounts_hub_page`, `summarize_open_hub_type`; decided by Claude under the reviewer's delegation (2026-11-11): a parameter keeps one clock in the app and makes the DAO deterministic; G1)*
**Integration-only behavior:** none.

**Model facts (table `account_invoices`, class `app.models.account_invoice.AccountInvoice`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `account_id` | Integer NOT NULL, FK `accounts.id` ON DELETE RESTRICT (no workspace check in the database) | — |
| `order_type` | String(30) nullable (`purchase_order` / `expense_order` / `sales_order` / `work_order`; free text today, BUG-624) | `NULL` |
| `order_id` | Integer nullable, **no FK** (polymorphic) | `NULL` |
| `invoice_type` | String(20) NOT NULL (`payable` / `receivable`) | — |
| `invoice_status` | String(20) NOT NULL (`draft` / `confirmed` / `voided`) | Python `'draft'` |
| `invoice_amount` | Numeric(15, 2) NOT NULL | — |
| `paid_amount` | Numeric(15, 2) NOT NULL | Python `0` |
| `payment_status` | String(20) NOT NULL (`unpaid` / `partial` / `paid`; `overdue` is documented but never stored, BUG-635) | Python `'unpaid'` |
| `invoice_number`, `vendor_invoice_number` | String(100) nullable | `NULL` |
| `invoice_date` | Date NOT NULL | — |
| `due_date` | Date nullable | `NULL` |
| `allow_payments` | Boolean NOT NULL | Python `True` |
| `receiving_started` | Boolean NOT NULL | Python `False` |
| `payment_locked_reason`, `description`, `notes`, `void_note` | Text nullable | `NULL` |
| `last_synced_at` | DateTime nullable | `NULL` |
| `created_at` | DateTime NOT NULL | database `now()` |
| `created_by`, `updated_by` | FK `profiles.id` nullable | `NULL` |
| `updated_at` | DateTime nullable, `onupdate=now()` | `NULL` |
No soft-delete column (drafts are hard-deleted by the manager; confirmed invoices are voided). Accounts (`accounts`) have `is_active`, `is_deleted`, `allow_invoices`; account names are not unique.

**Notes for the test designer:**
- `from app.dao.account_invoice import account_invoice_dao`. Rows: `make_workspace` (`tests/unit/factories.py`), `Account(workspace_id, name)`, `AccountInvoice(workspace_id, account_id, invoice_type, invoice_amount, invoice_date, …)` — set `invoice_status`, `payment_status`, `paid_amount` explicitly.
- Order-number search needs order rows: `purchase_orders.po_number`, `expense_orders.expense_number`, `sales_orders.sales_order_number`, `work_orders.work_order_number`, each with `workspace_id` and `invoice_id`. Their parents are heavy; see the manager spec's notes (G14) for which order kinds can be non-live. Only `work_orders` has `is_deleted`.
- An invoice on another workspace's account (BUG-2690) is a valid insert: the database checks only that the account exists.
- Rules tagged `[BUG-NNN]` state the **intended** behaviour; the `*(Today: …)*` note says what happens now.
- (G2) **Voided invoice, as a real void writes it** (`AccountInvoiceManager.void_invoice`, manager spec R5/R6): `invoice_status = "voided"`, `void_note` = the note, `paid_amount = 0.00`, `payment_status = "unpaid"`, `invoice_amount` unchanged, `updated_by` = the user (BUG-633; not written today), `updated_at` set by the column's `onupdate`; `allow_payments` is **not** touched. This DAO reads only `invoice_status`, so a test row needs only that, but a realistic voided row has `paid_amount 0.00` and `payment_status "unpaid"`. Invoices have no soft delete: drafts are hard-deleted, so a deleted invoice is simply absent.
- (2026-11-11, delegated) HR-16 cards that insert an invoice of workspace 1 on workspace 2's account (or order rows of another workspace) build **invalid data on purpose**; keep them as read checks that the row's ids, names and amounts never leak into workspace 1's lists, totals and KPIs (BUG-2690), not as a supported state. Decided by Claude under the reviewer's delegation (2026-11-11): HR-16 treats such rows as invalid data, and the read side must stay safe while old rows exist.
- (G1) Overdue cards after BUG-635: pass `today=` explicitly (e.g. `date(2026, 6, 15)`); a `due_date` of `today` minus one day is overdue, `today` is not, `NULL` never.

## Not specified
- `AccountInvoiceDAO.get_by_order` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-10); Q1).
- `account_invoice_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec.

---

## `AccountInvoiceDAO._escape_ilike(value)`
**Shape:** helper
**Persistence:** pure
**Visibility:** internal (used by: `_invoice_number_search_ilike_term`)

**Purpose:** make user text literal inside an `ILIKE` pattern with escape character `\`.

**Rules:**
- **R1.** Every `\` becomes `\\`, then every `%` becomes `\%` and every `_` becomes `\_`: `a%b_c\d` → `a\%b\_c\\d`. Other characters, case and whitespace are unchanged; `""` → `""`.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO._invoice_number_search_ilike_term(raw)`
**Shape:** helper
**Persistence:** pure
**Visibility:** internal (used by: `_build_filtered_query`)

**Rules:**
- **R1.** Leading/trailing whitespace is stripped; an empty result returns `""` (an empty pattern, not `%%`).
- **R2.** Otherwise returns `%<escaped>%` with the escaping of `_escape_ilike` R1: `" PO-1 "` → `%PO-1%`, `"50%"` → `%50\%%`.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO._outstanding_amount_expr()`
**Shape:** helper
**Persistence:** pure
**Visibility:** internal (used by: `_open_balance_subquery`, `summarize_open_hub_type`, `summarize_invoices`)

**Rules:**
- **R1.** The SQL value `invoice_amount − paid_amount`. It does **not** treat voided invoices as 0 (unlike the model's `outstanding_amount`); every caller leaves voided invoices out first. An overpaid invoice gives a negative value, and sums include it as such (verified: a 10.00 invoice paid 15.00 lowers `summarize_invoices`' outstanding total by 5.00). No path through the API overpays an invoice today (`create_payment` refuses more than the outstanding amount).

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO._order_number_search_conditions(db, *, workspace_id, term)`
**Shape:** helper
**Persistence:** reads (builds sub-selects)
**Visibility:** internal (used by: `_build_filtered_query`)

**Purpose:** match invoices whose linked order's number matches the pattern.

**Rules:**
- **R1.** An invoice matches when, for any of the four order kinds — purchase order (`po_number`), expense order (`expense_number`), sales order (`sales_order_number`), work order (`work_order_number`) — an order of **this workspace** whose number `ILIKE`s `term` (escape `\`) is linked to it either way:
  - forward: the invoice's `order_type` is exactly that kind's name (`purchase_order`, `expense_order`, `sales_order`, `work_order`; case-sensitive) and its `order_id` is that order's id;
  - reverse: that order's `invoice_id` is the invoice's id (orders with no invoice ignored).
- **R2.** Orders of another workspace never match, whatever their number or link.
- **R3.** A forward link with an `order_type` outside the four exact names (e.g. `"Purchase_Order"`, BUG-624) never matches by order number.
- **R4.** [BUG-2691] (HR-4) A soft-deleted work order (`is_deleted = True`) matches through neither link. Purchase, expense and sales orders have no soft-delete column; a voided purchase or expense order still matches. *(Today: a deleted work order's number still matches — verified.)*

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO._build_filtered_query(db, *, workspace_id, account_id=None, invoice_type=None, payment_status=None, invoice_status=None, invoice_number_search=None, account_name_search=None, invoice_date_from=None, invoice_date_to=None, due_date_from=None, due_date_to=None, amount_min=None, amount_max=None, open_balance_only=False)`
**Shape:** helper (query builder; the shared filter rules)
**Persistence:** reads
**Visibility:** internal (used by: `list_invoices`, `list_invoices_page_filtered`, `summarize_open_hub_type`, `count_accounts_with_any_open_balance`, `summarize_invoices`)

**Purpose:** the invoice query with every list filter; each caller adds order, paging or aggregates.

**Rules:**
- **R1.** Only invoices with `workspace_id` = the given workspace.
- **R2.** Invoices whose account is soft-deleted (`accounts.is_deleted = True`) are left out. Invoices of inactive accounts (`is_active = False`) are kept.
- **R2a.** [BUG-2690] (HR-16) An invoice whose account belongs to another workspace is left out, like one with no account: it is not listed, not matched by `account_name_search`, not counted and adds nothing to any total. *(Today: the account is joined by id only — such an invoice is listed with the foreign `account_id` and counted; verified.)*
- **R3.** Draft, confirmed and voided invoices are all kept unless a filter below removes them.
- **R4.** `account_id` not `None` (`0` included) → only invoices with that `account_id`.
- **R5.** `invoice_type`, `payment_status`, `invoice_status`: each, when truthy, is exact, case-sensitive equality on its column; `None` or `""` → no filter; an unknown value → nothing matches.
- **R5a.** [BUG-635] `payment_status = "overdue"` is a derived filter: confirmed invoices with `payment_status` `unpaid` or `partial` and a `due_date` before the `today` parameter (due on `today` is not overdue; no due date never is) (see the manager spec, `list_invoices` R5a, and *Externals*). *(Today: column equality with a value never stored — always empty.)*
- **R6.** `invoice_date_from` / `invoice_date_to` (truthy) → inclusive bounds on `invoice_date`.
- **R7.** `due_date_from` / `due_date_to` (truthy) → inclusive bounds on `due_date`; an invoice with no due date is left out whenever either bound is given.
- **R8.** `amount_min` / `amount_max` not `None` (`0` included) → inclusive bounds on `invoice_amount`.
- **R9.** `invoice_number_search` (truthy, not blank after trimming) matches, case-insensitively as a substring with `%`, `_`, `\` literal, any of: `invoice_number`, `vendor_invoice_number`, or a linked order's number per `_order_number_search_conditions` R1–R4. Invoices with a `NULL` number simply fail that branch.
- **R9a.** [BUG-637] A whitespace-only `invoice_number_search` is no filter. *(Today: it becomes the empty pattern, which matches only invoices whose invoice or vendor number is exactly `""` — verified 0 rows.)* `""` and `None` are no filter today already.
- **R10.** [BUG-622] (HR-8) When the trimmed search consists only of ASCII `0-9`, an invoice whose `id` equals that number also matches; other digit characters (`"²"`, `"١٢"`) are searched as text only and never raise. *(Today: Unicode `isdigit()` — `"²"` raises `ValueError`, verified; `"١٢"` matches id 12.)*
- **R11.** [BUG-622] (HR-8) `account_name_search` (truthy) → case-insensitive substring of the account name, `%`, `_`, `\` literal; not trimmed (a leading space is part of the text). *(Today: not escaped — `%` or `_` matches every account.)*
- **R12.** `open_balance_only=True` → [BUG-634] only invoices with `invoice_status = "confirmed"` and `payment_status` in `unpaid` / `partial`. *(Today: any non-voided invoice — drafts included — with `payment_status` in `unpaid`/`partial`/`overdue`.)* `False` → no condition.
- **R13.** All given filters combine with AND.

**Errors:** none of its own (R10 today: `ValueError`).
**Side effects:** none.

---

## `AccountInvoiceDAO.list_invoices(db, *, workspace_id, …filters…, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceManager.list_invoices` ← `GET /invoices/`, which passes every filter, `skip ≥ 0`, `limit` 1–1000)

**Rules:**
- **R1.** The invoices matching `_build_filtered_query` R1–R13 (never with `open_balance_only`).
- **R2.** Ordered by `invoice_date` descending, then `id` descending.
- **R3.** `skip` / `limit` applied after filtering and ordering; defaults 0 / 100. Returns a list (empty when nothing matches).

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO.list_invoices_page(db, *, workspace_id, account_id, open_balance_only=False, prioritize_purchase_order_id=None, skip=0, limit=10)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceManager.list_open_invoices_page` ← `GET /accounts/{id}/open-invoices/`, always with `open_balance_only=True`, `limit` 1–100)

**Rules:**
- **R1.** Same result as `list_invoices_page_filtered` with only these arguments (no other filter): `(items, total)` per its R1–R4. `open_balance_only=False` (never passed by a caller) lists all the account's invoices.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO._open_balance_subquery(db, *, workspace_id, invoice_type)`
**Shape:** helper (aggregate sub-select)
**Persistence:** reads
**Visibility:** internal (used by: `list_accounts_hub_page`)

**Purpose:** per account, the open balance of one invoice type.

**Rules:**
- **R1.** One row per account that has at least one counted invoice: invoices of this workspace, of the given `invoice_type`, on an account that is not soft-deleted, [BUG-634] `invoice_status = "confirmed"` with `payment_status` `unpaid`/`partial`. *(Today: any non-voided invoice — drafts included — with `payment_status` `unpaid`/`partial`/`overdue`.)*
- **R1a.** [BUG-2690] (HR-16) An invoice on another workspace's account is not counted. *(Today: it is grouped under that account's id; since the hub only lists this workspace's accounts, nothing of it is visible — no observable change on the hub page.)*
- **R2.** Columns: `outstanding_total` = sum of `invoice_amount − paid_amount` (`_outstanding_amount_expr` R1), `open_count` = number of counted invoices, `has_overdue` = 1 if any counted invoice is overdue else 0 — [BUG-635] overdue = `due_date` before today (manager spec `list_accounts_hub_page` R3). *(Today: 1 only when `payment_status = "overdue"`, never stored — always 0.)*

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO.list_accounts_hub_page(db, *, workspace_id, section="overview", search=None, skip=0, limit=50)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceManager.list_accounts_hub_page` ← `AccountService.get_accounts_hub_page` ← `GET /accounts/hub/`; `section` limited to `overview|payable|receivable` by the endpoint, `limit` 1–500)

**Purpose:** paged accounts of the workspace with their payable and receivable open balances.

**Returns:** `(rows, total)`; each row `(account, payable_agg, receivable_agg)` per `_reshape_accounts_hub_row`.

**Rules:**
- **R1.** [BUG-636] Accounts of this workspace that are not soft-deleted and are either active or have an open balance of either type (per `_open_balance_subquery` R1). *(Today: only active, not-deleted accounts.)* Accounts with no invoices are included.
- **R2.** Each account's `payable_agg` / `receivable_agg` comes from `_open_balance_subquery` for that type; an account with no counted invoice of a type → `0`, `0`, `False`.
- **R3.** `section = "payable"` → only accounts whose payable `outstanding_total > 0`; `"receivable"` → receivable `> 0`; any other value (`"overview"`, `""`, unknown) → no balance filter.
- **R4.** [BUG-622] (HR-8) `search` (truthy) → case-insensitive substring of the account name, `%`, `_`, `\` literal. *(Today: unescaped.)*
- **R5.** [BUG-623] (HR-6) Ordered by account name case-insensitively ascending, then `id` ascending. *(Today: `ORDER BY accounts.name ASC, accounts.id ASC` — case-sensitive, verified SQL.)*
- **R6.** `total` = number of accounts after R1, R3, R4, before paging; `skip` / `limit` (defaults 0 / 50) applied after ordering.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO._reshape_accounts_hub_row(row)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `list_accounts_hub_page`)

**Rules:**
- **R1.** Input is a 9-wide row: the account, then the payable sub-select's `account_id, outstanding_total, open_count, has_overdue`, then the receivable's same four. Returns `(account, payable_agg, receivable_agg)`; each agg is an object with attributes `outstanding_total`, `open_count`, `has_overdue` taken from positions 2–4 (payable) and 6–8 (receivable).
- **R2.** A `None` value (no sub-select row for that account) becomes `0` for `outstanding_total` and `open_count`, `False` for `has_overdue`; a non-`None` `has_overdue` is converted with `bool` (`1` → `True`, `0` → `False`). Values are otherwise passed through (`outstanding_total` stays a `Decimal`).

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO.summarize_open_hub_type(db, *, workspace_id, invoice_type)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceManager.get_invoices_hub_summary` ← `GET /invoices/hub-summary/`, once per type)

**Returns:** `(open_count: int, outstanding_total: Decimal, overdue_count: int, accounts_with_open_count: int)`.

**Rules:**
- **R1.** Counted set = `_build_filtered_query` with `invoice_type` and `open_balance_only=True` (R1, R2, R2a, R12): open, confirmed invoices of the type, accounts not soft-deleted (inactive accounts **count**).
- **R2.** `open_count` = number of counted invoices; `outstanding_total` = `Decimal` sum of `invoice_amount − paid_amount` over them, equal to 0 (`Decimal('0')`) when none; `accounts_with_open_count` = number of distinct accounts among them (0 when none).
- **R3.** [BUG-635] `overdue_count` = counted invoices with a `due_date` before today (manager spec `get_invoices_hub_summary` R2); no due date → never overdue. *(Today: counts `payment_status = "overdue"` — always 0.)*
- **R4.** An `invoice_type` other than `payable` / `receivable` (no caller does this) → `(0, 0, 0, 0)`.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO.count_accounts_with_any_open_balance(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceManager.get_invoices_hub_summary`)

**Rules:**
- **R1.** Number of distinct accounts with at least one invoice in `_build_filtered_query` with `open_balance_only=True` (either type); `0` when none. An account with both a payable and a receivable open invoice counts once.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO.list_invoices_page_filtered(db, *, workspace_id, account_id=None, …filters…, open_balance_only=False, prioritize_purchase_order_id=None, skip=0, limit=10)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `list_invoices_page`; `AccountInvoiceManager.list_invoices_page` ← `AccountInvoiceService.list_account_invoices_page` ← `GET /accounts/{id}/invoices/`, which always passes `account_id` and never `account_name_search`, `amount_min`, `amount_max`, `open_balance_only` or `prioritize_purchase_order_id`; `limit` 1–1000)

**Returns:** `(items, total)`.

**Rules:**
- **R1.** Matching set = `_build_filtered_query` R1–R13 with every argument passed through.
- **R2.** `total` = number of matching invoices, ignoring `skip` / `limit`.
- **R3.** `prioritize_purchase_order_id` not `None` → invoices with `order_type = "purchase_order"` and `order_id` equal to it come first; inside each group, `invoice_date` descending then `id` descending. This includes the receivable credit notes of that purchase order's returns (they carry the same link) — intended (decided by Claude under the reviewer's delegation (2026-11-10): ordering only, and the credit note belongs to that order). An order linked only through `purchase_orders.invoice_id` is not prioritised. `None` → `invoice_date` descending, `id` descending.
- **R4.** `skip` / `limit` applied after ordering; defaults 0 / 10.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO.summarize_invoices(db, *, workspace_id, …filters…)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceManager.summarize_invoices` ← `GET /accounts/{id}/invoice-summary/`, which always passes `account_id` and never `account_name_search`; the web app's account KPI strip passes no other filter)

**Returns:** [BUG-2692] a 7-tuple, see R5. *(Today: `(invoice_count: int, invoiced_total: Decimal, paid_total: Decimal, outstanding_total: Decimal)`.)*

**Rules:**
- **R1.** Matching set = `_build_filtered_query` R1–R11, R13 (never `open_balance_only`), no paging.
- **R2.** `invoice_count` = all matching invoices, voided and drafts included.
- **R3.** Money totals over matching invoices that are not voided and, [BUG-634], are `confirmed`: sum of `invoice_amount`, sum of `paid_amount`, sum of `invoice_amount − paid_amount`. *(Today: drafts are included.)*
- **R4.** With nothing to sum, each total is a `Decimal` equal to 0 (`Decimal('0')`, verified). After BUG-2692 this holds for each type's triple.
- **R5.** [BUG-2692] Money is never added across invoice types. The result is `(invoice_count, payable_invoiced, payable_paid, payable_outstanding, receivable_invoiced, receivable_paid, receivable_outstanding)`: each triple sums R3 over the matching invoices of that `invoice_type` only, and `invoice_count` is R2 (both types). A 1,000.00 unpaid confirmed payable and a 200.00 unpaid confirmed receivable on one account give payable `(1000.00, 0.00, 1000.00)` and receivable `(200.00, 0.00, 200.00)`. With `invoice_type="payable"` the receivable triple is 0 (R4), and the reverse. *(requires a new return shape. Today: one triple summed over both types — the example gives `invoiced_total` 1,200.00, `outstanding_total` 1,200.00, verified 2026-11-10.)*

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceDAO.update_paid_amount(db, *, invoice_id, workspace_id, additional_payment)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `InvoicePaymentManager.create_payment` ← `POST /invoice-payments/`, after it has locked the invoice and checked it is confirmed, allows payments and has enough outstanding; `payment_amount` is `> 0` by schema)

**Purpose:** add a payment to an invoice's paid amount and refresh its payment status.

**Returns:** the `AccountInvoice` (flushed, not committed), or `None`.

**Rules:**
- **R1.** No invoice with that id in the workspace (unknown id, or an invoice of another workspace) → returns `None`, nothing written.
- **R2.** `paid_amount` increases by `additional_payment`, and the row is flushed. Postgres stores it rounded half away from zero to 2 places (HR-15); the returned object keeps the unrounded in-memory value until refreshed (verified `999.995` → in memory `999.995`, stored `1000.00`). More than 2 decimals reaching here is BUG-604 (payment schema).
- **R3.** New `paid_amount` ≥ `invoice_amount` → `payment_status = "paid"` (equal included, and a 0.00 invoice with a 0 payment).
- **R4.** Otherwise, new `paid_amount` > 0 → `"partial"`.
- **R5.** Otherwise (new `paid_amount` ≤ 0 — only with a zero or negative `additional_payment`, which no caller can send) `payment_status` is left as it was (verified: `-100` on a paid 100.00 invoice → `paid_amount 0.00`, status still `paid`). Unreachable; described, not asked.
- **R6.** The status is decided on the in-memory (unrounded) sum, before the database rounds it (verified `999.995` on a 1,000.00 invoice → `partial`, stored `1000.00`; BUG-604 is the fix, upstream).
- **R7.** It does not look at `invoice_status`, `allow_payments` or the outstanding balance (a voided invoice is updated too — verified → `partial`), and takes no row lock of its own. Both are the caller's preconditions: `create_payment` locks the row `FOR UPDATE` and runs every check first (decided by Claude under the reviewer's delegation (2026-11-10): intended).
- **R8.** No other field is written (no `updated_by`; `updated_at` moves by the model's `onupdate`). Positional arguments raise `TypeError`.

**Errors:** none of its own.

**Side effects:** `paid_amount`, `payment_status` (and `updated_at`) on one invoice; flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 26–27 | escape `\`, `%`, `_` | `_escape_ilike` R1 |
| 33 | stripped empty → `""` | `_invoice_number_search_ilike_term` R1 |
| 35 | non-empty → `%…%` | `_invoice_number_search_ilike_term` R2 |
| 40 | outstanding expression | `_outstanding_amount_expr` R1 |
| 57 | loop over four order kinds | `_order_number_search_conditions` R1, R3 |
| 58–61, 68–72 | order sub-selects scoped by workspace (no `is_deleted`) | `_order_number_search_conditions` R2, R4 |
| 70 | reverse link ignores orders with no invoice | `_order_number_search_conditions` R1 |
| 101–105 | join account, workspace, account not deleted (no account workspace) | `_build_filtered_query` R1, R2, R2a |
| 108 | `account_id is not None` | `_build_filtered_query` R4 |
| 110, 112, 114 | truthy type / payment status / invoice status | `_build_filtered_query` R5, R5a |
| 116 | truthy `invoice_number_search` | `_build_filtered_query` R9, R9a |
| 128 | `raw.isdigit()` | `_build_filtered_query` R10 |
| 131 | truthy `account_name_search` | `_build_filtered_query` R11 |
| 133, 135 | invoice date bounds | `_build_filtered_query` R6 |
| 137, 139 | due date bounds | `_build_filtered_query` R7 |
| 141, 143 | amount bounds `is not None` | `_build_filtered_query` R8 |
| 145 | `open_balance_only` | `_build_filtered_query` R12 |
| 190–195 | order, offset, limit | `list_invoices` R2, R3 |
| 210 | delegates | `list_invoices_page` R1 |
| 222–241 | open-balance sub-select filters and aggregates | `_open_balance_subquery` R1, R1a, R2 |
| 263–272 | accounts of workspace, active, not deleted | `list_accounts_hub_page` R1, R2 |
| 274 / 276 / else | section payable / receivable / other | `list_accounts_hub_page` R3 |
| 279 | truthy `search` | `list_accounts_hub_page` R4 |
| 282–288 | count, order, page | `list_accounts_hub_page` R5, R6 |
| 301–303 | `None` → 0 / 0 / `False`; `bool()` | `_reshape_accounts_hub_row` R2 |
| 306 | positions 1 and 5 | `_reshape_accounts_hub_row` R1 |
| 322–331 | counts, sum, overdue, distinct accounts; `or 0` | `summarize_open_hub_type` R1–R4 |
| 344–347 | distinct accounts; `or 0` | `count_accounts_with_any_open_balance` R1 |
| 389 | total before paging | `list_invoices_page_filtered` R2 |
| 391 / else | prioritise PO / plain order | `list_invoices_page_filtered` R3 |
| 411 | offset, limit | `list_invoices_page_filtered` R4 |
| 453 | count incl. voided | `summarize_invoices` R2 |
| 455–459 | money totals exclude voided; coalesce 0 | `summarize_invoices` R3, R4, R5 |
| 485–486 | invoice found in workspace | `update_paid_amount` R1 |
| 487 | add payment | `update_paid_amount` R2, R6 |
| 489 / 491 / neither | paid / partial / unchanged | `update_paid_amount` R3, R4, R5 |
| 494 | flush | `update_paid_amount` R2 |
| 468–479 | `get_by_order` | Not specified (dead code) |

## Gap log
- G1 (account_invoice.cases.md gap 1) — Intent, decided by Claude under the reviewer's delegation (2026-11-11) — "today" after BUG-635 is a keyword parameter `today: date` passed by the manager (one clock, read once in the manager via `app.managers.account_invoice_manager.utcnow`); the DAO reads no clock and needs no patch. Overview *Externals*, `_build_filtered_query` R5a, Notes updated.
- G2 (account_invoice.cases.md gap 2) — Fact — a real void writes `invoice_status`, `void_note`, `paid_amount = 0.00`, `payment_status = "unpaid"`, `updated_at` (onupdate) and, after BUG-633, `updated_by`; not `allow_payments`. The designer's assumption is corrected (paid amount and payment status are also reset). Notes updated.
