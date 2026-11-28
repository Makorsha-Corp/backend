# Fix brief: dao-account_invoice

## 1. Unit

| | |
|---|---|
| Slug | `dao-account_invoice` |
| Source file | `app/dao/account_invoice.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-account_invoice` |
| Branch | `bugfix/dao-account_invoice` (from `origin/main`) |
| Risk | `normal`: the file feeds invoice lists, money totals and hub KPIs (money), so it can never be trivial; every bug's intended behaviour is already settled by its row, the spec and the house rules (HR-4, HR-6, HR-8, HR-16), so no owner question is open. No migration. |

Bugs in this unit: BUG-622, BUG-623, BUG-2690, BUG-2691. (BUG-637 was planned here too but is **not** in this unit: see §6.)

## 2. Bugs

### BUG-622: Invoice/account search filters are not HR-8 safe
- **Pattern:** `unescaped-like-wildcards`
- **Where:** `AccountInvoiceDAO._build_filtered_query` (`account_name_search`, and the digit-only id shortcut of `invoice_number_search`) and `AccountInvoiceDAO.list_accounts_hub_page` (`search`); reached through `GET /invoices/` and `GET /accounts/hub/`.
- **Today:** `account_name_search` (used by `list_invoices` and every other caller of the shared filter) and the hub `search` are placed in `ILIKE '%…%'` unescaped (`%` or `_` matches everything; `\` acts as the escape character). The digit-only id-match shortcut of `invoice_number_search` uses Unicode `isdigit()`: `"²"` raises `ValueError` (a 500), `"١٢"` (Arabic-Indic digits) matches invoice id 12.
- **Intended:** `%`, `_` and `\` matched literally in both name searches; only ASCII `0-9` triggers the id-match shortcut; other digit characters are searched as text only and never raise.
- **Example:** A user types `%` into the account-name box of the invoices page and gets every invoice of every account, instead of only those of "100% Cotton".

### BUG-623: Accounts-hub page ordered by account name case-sensitively
- **Pattern:** `hr-6-non-default-list-order`
- **Where:** `AccountInvoiceDAO.list_accounts_hub_page`; reached through `GET /accounts/hub/`.
- **Today:** Orders by account name case-sensitively (`"apex"` sorts after `"Zeta"`), then `id`.
- **Intended:** Order by name case-insensitive ascending, then `id` ascending.

### BUG-2690: An invoice on another workspace's account is listed, found by that account's name and counted in totals
- **Pattern:** `cross-workspace-row-exposed`
- **Where:** `AccountInvoiceDAO._build_filtered_query`, `AccountInvoiceDAO._open_balance_subquery`; reached through `GET /invoices/`, `GET /invoices/hub-summary/`, `GET /accounts/{id}/invoice-summary/`, `/open-invoices/`, `/invoices/`.
- **Today:** The account is joined by id only: an invoice of workspace A whose `account_id` names workspace B's account is listed with B's account id, matched by `account_name_search` on B's account name, and counted in A's summary and hub KPIs (seen: A's payable KPI said 2 open / 1,050.00 / 2 accounts while A's hub page showed one account with 1,000.00).
- **Intended:** HR-16, per BUG-1086 / BUG-1801: such an invoice is treated as not found — left out of every list, count and total, in the query before paging, by requiring the account's `workspace_id` to equal the invoice's; the row stays for a one-off clean-up (decided by Claude under the reviewer's delegation (2026-11-10)).
- **Example:** Workspace "Dhaka Mills" has one 1,000.00 bill on its own supplier and, through bad old data, one 50.00 bill pointing at a supplier of another workspace. Its hub KPI says "2 accounts, 1,050.00 open"; the correct figure is "1 account, 1,000.00".

### BUG-2691: A soft-deleted work order's number still finds its invoice
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `AccountInvoiceDAO._order_number_search_conditions`; reached through `invoice_number_search` on `GET /invoices/`, `GET /accounts/{id}/invoices/`, `/invoice-summary/`.
- **Today:** The order-number search reads `work_orders` without `is_deleted`: a deleted work order's number matches through the forward link (`order_type` / `order_id`) and the reverse link (`work_orders.invoice_id`).
- **Intended:** HR-4: a soft-deleted work order neither matches nor filters; the invoice stays visible and is still found by its own numbers; voided purchase/expense orders (a state, not a deletion) keep matching (decided by Claude under the reviewer's delegation (2026-11-10)).
- **Example:** Work order `WO-DEL-77` was deleted last week. Searching invoices for `wo-del-7` still returns the invoice it was linked to.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file:
- Table `account_invoices` (`app.models.account_invoice.AccountInvoice`): `workspace_id` NOT NULL; `account_id` NOT NULL, FK `accounts.id` ON DELETE RESTRICT, **no workspace check in the database** (an invoice on another workspace's account is a valid insert today: invalid data per HR-16); `order_type` String(30) nullable (`purchase_order` / `expense_order` / `sales_order` / `work_order`), `order_id` nullable with no FK (polymorphic link); `invoice_type` (`payable` / `receivable`); `invoice_status` (`draft` / `confirmed` / `voided`); `invoice_amount`, `paid_amount` Numeric(15, 2); `payment_status` (`unpaid` / `partial` / `paid`; `overdue` documented but never stored); `invoice_number`, `vendor_invoice_number` String(100) nullable; `invoice_date` NOT NULL, `due_date` nullable. No soft-delete column on invoices.
- `accounts` have `workspace_id`, `name` (not unique), `is_active`, `is_deleted`.
- Only `work_orders` has `is_deleted` among the four order tables; purchase, expense and sales orders have no soft-delete column (a voided purchase/expense order is a state).
- Every parameter after `db` is keyword-only. The class never commits; only `update_paid_amount` flushes.
- The escape character for every `ILIKE` here is `\` (`_ILIKE_ESCAPE`).

### `AccountInvoiceDAO._escape_ilike(value)` (helper; must not change)
- **R1.** Every `\` becomes `\\`, then every `%` becomes `\%` and every `_` becomes `\_`: `a%b_c\d` → `a\%b\_c\\d`. Other characters, case and whitespace are unchanged; `""` → `""`.

### `AccountInvoiceDAO._invoice_number_search_ilike_term(raw)` (helper; must not change)
- **R1.** Leading/trailing whitespace is stripped; an empty result returns `""` (an empty pattern, not `%%`).
- **R2.** Otherwise returns `%<escaped>%` with the escaping of `_escape_ilike` R1: `" PO-1 "` → `%PO-1%`, `"50%"` → `%50\%%`.

### `AccountInvoiceDAO._outstanding_amount_expr()` (helper; must not change)
- **R1.** The SQL value `invoice_amount − paid_amount`. It does not treat voided invoices as 0; every caller leaves voided invoices out first. An overpaid invoice gives a negative value, and sums include it as such.

### `AccountInvoiceDAO._order_number_search_conditions(db, *, workspace_id, term)`
Purpose: match invoices whose linked order's number matches the pattern.
- **R1.** An invoice matches when, for any of the four order kinds — purchase order (`po_number`), expense order (`expense_number`), sales order (`sales_order_number`), work order (`work_order_number`) — an order of **this workspace** whose number `ILIKE`s `term` (escape `\`) is linked to it either way:
  - forward: the invoice's `order_type` is exactly that kind's name (`purchase_order`, `expense_order`, `sales_order`, `work_order`; case-sensitive) and its `order_id` is that order's id;
  - reverse: that order's `invoice_id` is the invoice's id (orders with no invoice ignored).
- **R2.** Orders of another workspace never match, whatever their number or link.
- **R3.** A forward link with an `order_type` outside the four exact names (e.g. `"Purchase_Order"`) never matches by order number.
- **R4.** [BUG-2691] (HR-4) A soft-deleted work order (`is_deleted = True`) matches through neither link. Purchase, expense and sales orders have no soft-delete column; a voided purchase or expense order still matches. *(Today: a deleted work order's number still matches.)* The invoice itself stays visible and is still found by its own `invoice_number` / `vendor_invoice_number` and by any other live linked order.

### `AccountInvoiceDAO._build_filtered_query(db, *, workspace_id, account_id=None, invoice_type=None, payment_status=None, invoice_status=None, invoice_number_search=None, account_name_search=None, invoice_date_from=None, invoice_date_to=None, due_date_from=None, due_date_to=None, amount_min=None, amount_max=None, open_balance_only=False)`
The shared filter rules; used by `list_invoices`, `list_invoices_page_filtered` (and through it `list_invoices_page`), `summarize_open_hub_type`, `count_accounts_with_any_open_balance`, `summarize_invoices`. Each caller adds order, paging or aggregates.
- **R1.** Only invoices with `workspace_id` = the given workspace.
- **R2.** Invoices whose account is soft-deleted (`accounts.is_deleted = True`) are left out. Invoices of inactive accounts (`is_active = False`) are kept.
- **R2a.** [BUG-2690] (HR-16) An invoice whose account belongs to another workspace is left out, like one with no account: it is not listed, not matched by `account_name_search`, not counted and adds nothing to any total. This holds whatever the other filters, including when `account_id` names that foreign account (then the result is empty, total 0). *(Today: the account is joined by id only — such an invoice is listed with the foreign `account_id` and counted.)*
- **R3.** Draft, confirmed and voided invoices are all kept unless a filter below removes them.
- **R4.** `account_id` not `None` (`0` included) → only invoices with that `account_id`.
- **R5.** `invoice_type`, `payment_status`, `invoice_status`: each, when truthy, is exact, case-sensitive equality on its column; `None` or `""` → no filter; an unknown value → nothing matches.
- **R5a.** (BUG-635, **not in this unit**, see §6.) Leave today's behaviour: `payment_status="overdue"` is plain column equality.
- **R6.** `invoice_date_from` / `invoice_date_to` (truthy) → inclusive bounds on `invoice_date`.
- **R7.** `due_date_from` / `due_date_to` (truthy) → inclusive bounds on `due_date`; an invoice with no due date is left out whenever either bound is given.
- **R8.** `amount_min` / `amount_max` not `None` (`0` included) → inclusive bounds on `invoice_amount`.
- **R9.** `invoice_number_search` (truthy, not blank after trimming) matches, case-insensitively as a substring with `%`, `_`, `\` literal, any of: `invoice_number`, `vendor_invoice_number`, or a linked order's number per `_order_number_search_conditions` R1–R4. Invoices with a `NULL` number simply fail that branch.
- **R9a.** (BUG-637, **not in this unit**, see §6.) **Leave today's behaviour unchanged:** a whitespace-only `invoice_number_search` still becomes the empty pattern (it matches only invoices whose invoice or vendor number is exactly `""`). `""` and `None` are no filter. Do not change the `if invoice_number_search:` condition or the empty-pattern result.
- **R10.** [BUG-622] (HR-8) When the trimmed search consists only of ASCII `0-9`, an invoice whose `id` equals that number also matches; other digit characters (`"²"`, `"١٢"`) are searched as text only (through R9) and never raise. Trimming happens before the check (`"  12  "` still matches id 12); `"12x"` does not trigger the id match. *(Today: Unicode `isdigit()` — `"²"` raises `ValueError`; `"١٢"` matches id 12.)*
- **R11.** [BUG-622] (HR-8) `account_name_search` (truthy) → case-insensitive substring of the account name, `%`, `_`, `\` literal; **not trimmed** (a leading space is part of the text: `" acme"` finds "Big Acme"). *(Today: not escaped — `%` or `_` matches every account, `\` acts as the escape character.)* Example: `%` finds only "50% Off"; `_` only "A_B"; `k\S` finds `Back\Slash` and not `BackSlash`; a lone `\` finds only names containing a backslash.
- **R12.** `open_balance_only=True` → today's condition: not voided and `payment_status` in `unpaid` / `partial` / `overdue`. (Leaving out drafts is BUG-634, **not in this unit**, see §6.) `False` → no condition.
- **R13.** All given filters combine with AND.

Errors: none of its own (R10 today: `ValueError`). Side effects: none.

### `AccountInvoiceDAO.list_invoices(db, *, workspace_id, …filters…, skip=0, limit=100)`
Used by `AccountInvoiceManager.list_invoices` ← `GET /invoices/` (every filter, `skip ≥ 0`, `limit` 1–1000).
- **R1.** The invoices matching `_build_filtered_query` R1–R13 (never with `open_balance_only`).
- **R2.** Ordered by `invoice_date` descending, then `id` descending.
- **R3.** `skip` / `limit` applied after filtering and ordering; defaults 0 / 100. Returns a list (empty when nothing matches).

### `AccountInvoiceDAO.list_invoices_page(db, *, workspace_id, account_id, open_balance_only=False, prioritize_purchase_order_id=None, skip=0, limit=10)`
Used by `AccountInvoiceManager.list_open_invoices_page` ← `GET /accounts/{id}/open-invoices/` (always `open_balance_only=True`, `limit` 1–100).
- **R1.** Same result as `list_invoices_page_filtered` with only these arguments: `(items, total)` per its R1–R4. `open_balance_only=False` lists all the account's invoices. (After BUG-2690, an `account_id` of another workspace's account gives `([], 0)`.)

### `AccountInvoiceDAO.list_invoices_page_filtered(db, *, workspace_id, account_id=None, …filters…, open_balance_only=False, prioritize_purchase_order_id=None, skip=0, limit=10)`
Used by `list_invoices_page` and `AccountInvoiceManager.list_invoices_page` ← `GET /accounts/{id}/invoices/`. Returns `(items, total)`.
- **R1.** Matching set = `_build_filtered_query` R1–R13 with every argument passed through.
- **R2.** `total` = number of matching invoices, ignoring `skip` / `limit`.
- **R3.** `prioritize_purchase_order_id` not `None` → invoices with `order_type = "purchase_order"` and `order_id` equal to it come first; inside each group, `invoice_date` descending then `id` descending. An order linked only through `purchase_orders.invoice_id` is not prioritised. `None` → `invoice_date` descending, `id` descending.
- **R4.** `skip` / `limit` applied after ordering; defaults 0 / 10.

### `AccountInvoiceDAO._open_balance_subquery(db, *, workspace_id, invoice_type)`
Per account, the open balance of one invoice type; used by `list_accounts_hub_page`.
- **R1.** One row per account that has at least one counted invoice: invoices of this workspace, of the given `invoice_type`, on an account that is not soft-deleted, not voided, with `payment_status` `unpaid` / `partial` / `overdue` (today's condition; leaving out drafts is BUG-634, not in this unit).
- **R1a.** [BUG-2690] (HR-16) An invoice on another workspace's account is not counted (same join condition as `_build_filtered_query` R2a). *(Today: it is grouped under that account's id; since the hub only lists this workspace's accounts, nothing of it is visible — no observable change on the hub page is expected.)*
- **R2.** Columns: `outstanding_total` = sum of `invoice_amount − paid_amount`, `open_count` = number of counted invoices, `has_overdue` = 1 if any counted invoice has `payment_status = "overdue"` else 0 (today's rule; the derived overdue is BUG-635, not in this unit).

### `AccountInvoiceDAO.list_accounts_hub_page(db, *, workspace_id, section="overview", search=None, skip=0, limit=50)`
Used by `AccountInvoiceManager.list_accounts_hub_page` ← `AccountService.get_accounts_hub_page` ← `GET /accounts/hub/` (`section` limited to `overview|payable|receivable` by the endpoint, `limit` 1–500). Returns `(rows, total)`; each row `(account, payable_agg, receivable_agg)` per `_reshape_accounts_hub_row`.
- **R1.** Accounts of this workspace that are active and not soft-deleted (today's rule; admitting inactive accounts with an open balance is BUG-636, not in this unit). Accounts with no invoices are included.
- **R2.** Each account's `payable_agg` / `receivable_agg` comes from `_open_balance_subquery` for that type; an account with no counted invoice of a type → `0`, `0`, `False`.
- **R3.** `section = "payable"` → only accounts whose payable `outstanding_total > 0`; `"receivable"` → receivable `> 0`; any other value (`"overview"`, `""`, unknown) → no balance filter.
- **R4.** [BUG-622] (HR-8) `search` (truthy) → case-insensitive substring of the account name, `%`, `_`, `\` literal. *(Today: unescaped.)* Example: `%` finds only "50% Off"; `_` only "A_B"; `k\S` finds `Back\Slash` and not `BackSlash`.
- **R5.** [BUG-623] (HR-6) Ordered by account name case-insensitively ascending, then `id` ascending. Account names are not unique, so equal or case-insensitively equal names are a real case and are ordered by `id`: "APEX" (id 1), "Zeta" (2), "Beta" (3), "apex" (4) → APEX, apex, Beta, Zeta; "acme" (1), "Acme" (2), "acme" (3) → 1, 2, 3. *(Today: `ORDER BY accounts.name ASC, accounts.id ASC` — case-sensitive.)* Codebase convention for this order: the lower-cased name ascending, then id ascending (as in `app/dao/account_tag.py`, `app/dao/item_tag.py`, `app/dao/factory_section.py`).
- **R6.** `total` = number of accounts after R1, R3, R4, before paging; `skip` / `limit` (defaults 0 / 50) applied after ordering.

### `AccountInvoiceDAO._reshape_accounts_hub_row(row)` (mapper; must not change)
- **R1.** Input is a 9-wide row: the account, then the payable sub-select's `account_id, outstanding_total, open_count, has_overdue`, then the receivable's same four. Returns `(account, payable_agg, receivable_agg)`; each agg has `outstanding_total`, `open_count`, `has_overdue` from positions 2–4 (payable) and 6–8 (receivable).
- **R2.** A `None` value becomes `0` for `outstanding_total` and `open_count`, `False` for `has_overdue`; a non-`None` `has_overdue` is converted with `bool`. Values are otherwise passed through (`outstanding_total` stays a `Decimal`).
- So the hub query must keep selecting exactly: the account, then the payable sub-select's four columns, then the receivable's four.

### `AccountInvoiceDAO.summarize_open_hub_type(db, *, workspace_id, invoice_type)`
Used by `AccountInvoiceManager.get_invoices_hub_summary` ← `GET /invoices/hub-summary/`, once per type. Returns `(open_count: int, outstanding_total: Decimal, overdue_count: int, accounts_with_open_count: int)`.
- **R1.** Counted set = `_build_filtered_query` with `invoice_type` and `open_balance_only=True` (R1, R2, R2a, R12); inactive accounts count.
- **R2.** `open_count` = number of counted invoices; `outstanding_total` = `Decimal` sum of `invoice_amount − paid_amount` over them, `Decimal('0')` when none; `accounts_with_open_count` = number of distinct accounts among them (0 when none).
- **R3.** `overdue_count` = counted invoices with `payment_status = "overdue"` (today's rule; BUG-635 not in this unit).
- **R4.** An `invoice_type` other than `payable` / `receivable` → `(0, 0, 0, 0)`.
- Example after BUG-2690: a 10.00 payable on the workspace's own account and a 40.00 payable on another workspace's account → `(1, 10.00, 0, 1)`.

### `AccountInvoiceDAO.count_accounts_with_any_open_balance(db, *, workspace_id)`
- **R1.** Number of distinct accounts with at least one invoice in `_build_filtered_query` with `open_balance_only=True` (either type); `0` when none. An account with both a payable and a receivable open invoice counts once. (After BUG-2690 a foreign account never counts.)

### `AccountInvoiceDAO.summarize_invoices(db, *, workspace_id, …filters…)`
Used by `AccountInvoiceManager.summarize_invoices` ← `GET /accounts/{id}/invoice-summary/`. **Keep today's return shape** `(invoice_count: int, invoiced_total: Decimal, paid_total: Decimal, outstanding_total: Decimal)` (splitting by type is BUG-2692, not in this unit).
- **R1.** Matching set = `_build_filtered_query` R1–R11, R13 (never `open_balance_only`), no paging.
- **R2.** `invoice_count` = all matching invoices, voided and drafts included.
- **R3.** Money totals over matching invoices that are not voided: sum of `invoice_amount`, sum of `paid_amount`, sum of `invoice_amount − paid_amount` (drafts are included today; BUG-634, not in this unit).
- **R4.** With nothing to sum, each total is a `Decimal` equal to 0 (`Decimal('0')`). Example after BUG-2690: `account_id` = another workspace's account (on which this workspace has an invoice) → `(0, 0, 0, 0)`.

### `AccountInvoiceDAO.update_paid_amount` and `get_by_order` (not in a bug; must not change)
- `update_paid_amount(db, *, invoice_id, workspace_id, additional_payment)`: finds the invoice with the inherited `get_by_id_and_workspace` (not found / other workspace → `None`), adds the payment to `paid_amount`, sets `payment_status` to `paid` when `paid_amount ≥ invoice_amount`, else `partial` when `> 0`, else leaves it; flushes. No lock of its own (the caller holds it). Leave it as it is.
- `get_by_order`: dead code; leave it (its removal is a separate change).

### Inherited `BaseDAO` methods (not overridden; must not change)
- `get`, `get_by_id_and_workspace`, `create`, `update`, `remove` stay raw; many managers and services use them. Do not change them or add filters to them.

## 4. Rules that apply

- **HR-4. Soft-deleted rows are hidden unless asked for.** Lists/searches exclude soft-deleted rows by default. Filters, joins and searches through related rows ignore related rows that are soft-deleted (e.g. a deleted tag neither filters nor matches). Scope: managers and module-specific DAO query methods; the generic `BaseDAO` methods stay raw.
- **HR-5. Filter first, then page.** All filtering happens in the query before `skip` / `limit`; a page is only short when there are no more results; counts and totals are taken after filtering.
- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. No order recipe counts as deterministic unless it ends in `id`.
- **HR-8. Search text is literal.** Text placed in `LIKE` / `ILIKE` patterns is escaped: `%` and `_` (and, per the bug row, `\`) match literally. Digit-only shortcuts (e.g. "search also matches id") accept ASCII `0-9` only and never raise on other input. This file already has a complete private `_escape_ilike` (it escapes `\`, `%` and `_`) and `_ILIKE_ESCAPE = "\\"`, used by the invoice-number search; reuse them with `escape=self._ILIKE_ESCAPE`, the same convention as `app/dao/help_ticket.py` and `app/dao/machine.py`.
- **HR-16. Nothing links across workspaces.** A row linking to another workspace's row is invalid data, never a normal state; no response shows another workspace's ids or names. On the read side such a row is treated as not found (per BUG-1086 / BUG-1801). Any join or subquery you add must stay bounded by the workspace.
- No owner answer (OQ-n) touches these bugs. (OQ-41, the split of the account summary by invoice type, belongs to BUG-2692, which is not in this unit.)

## 5. Scope

- May change: `app/dao/account_invoice.py` only.
- No migration, no schema, model or API change. Method names, signatures, keyword-only parameters, defaults and return shapes stay as they are (including the 4-value `summarize_invoices` result and the 9-wide hub row).
- `_escape_ilike` and `_invoice_number_search_ilike_term` keep their names and behaviour (§3).

## 6. Out of scope (leave alone)

- **BUG-637** (whitespace-only search treated as no filter). Its rule is shared by this file's `invoice_number_search` and by the account name search in `app/dao/account.py` (`get_accounts_in_workspace`, also reached through `AccountManager.search_accounts`). `app/dao/account.py` is another unit's file in this batch, so BUG-637 will be fixed later as one two-file unit. **Do not change the whitespace-only `invoice_number_search` behaviour here** (§3 `_build_filtered_query` R9a).
- **BUG-2692** (`summarize_invoices` adds payables and receivables into one total; owner OQ-41): needs a new return shape plus manager, schema, endpoint and web changes. Keep today's 4-value result.
- **BUG-634** (drafts counted in open balances and money totals), **BUG-635** (overdue never derived; needs a `today` parameter), **BUG-636** (hub list hides inactive accounts with an open balance): `app/managers/account_invoice_manager.py` bugs whose rules also touch this file's `_build_filtered_query` R12, R5a, `_open_balance_subquery` R1/R2, `summarize_open_hub_type` R3 and `list_accounts_hub_page` R1. Leave those conditions exactly as they are today.
- **BUG-624** (`order_type` free text; fix in the schema), **BUG-604** (payment decimals; payment schema).
- Other `app/managers/account_invoice_manager.py` bugs (BUG-620, BUG-621, BUG-625 … BUG-633, BUG-639, BUG-2730, BUG-2736, BUG-2788) and `app/services/account_invoice_service.py` bugs (BUG-2731 … BUG-2733, BUG-2962 … BUG-2969).
- `app/dao/account.py` bugs (BUG-1480, BUG-1481, and the account name-search part of BUG-637): another unit.
- Dead code `get_by_order`: leave it.
