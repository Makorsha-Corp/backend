# Impact review, round 1: dao-account_invoice

Date: 2026-11-28. Diff: `git diff origin/main -- app alembic` in
`E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-account_invoice` (one file, `app/dao/account_invoice.py`;
no migration). Bugs: BUG-622, BUG-623, BUG-2690, BUG-2691 (BUG-637 left out on purpose, untouched).

**Verdict: APPROVE.** No blocking finding. Contract: value-only changes, no frontend change (see `contract.md`).

## Changed functions

| Function | Change |
|---|---|
| `_same_workspace_account_join()` (new static helper) | `account_id = accounts.id AND accounts.workspace_id = account_invoices.workspace_id` |
| `_build_filtered_query` | join uses the helper; `account_name_search` escaped (`_escape_ilike`, `ESCAPE '\'`); id shortcut only on `isascii() and isdigit()` |
| `_open_balance_subquery` | join uses the helper |
| `_order_number_search_conditions` | `is_deleted = false` added to both sub-selects of any order model that has the column (only `WorkOrder`) |
| `list_accounts_hub_page` | `search` escaped; ORDER BY `lower(accounts.name) ASC, accounts.id ASC` |

## Upstream (every caller)

Grepped `account_invoice_dao`, `AccountInvoiceDAO` and each method name over `app/`.

- The changed queries are reached **only** through `AccountInvoiceManager` (`list_invoices`,
  `list_open_invoices_page`, `list_invoices_page`, `get_invoices_hub_summary`, `list_accounts_hub_page`,
  `summarize_invoices`) → `AccountInvoiceService` / `AccountService.get_accounts_hub_page` → endpoints
  `GET /account-invoices/`, `GET /account-invoices/hub-summary/`, `GET /accounts/hub/`,
  `GET /accounts/{id}/invoice-summary/`, `/open-invoices/`, `/invoices/`. All read-only.
- No caller re-sorts or re-filters: the hub service maps rows in order into dicts; the frontend shows server order
  (no client sort on `AccountsLandingPage` / `AccountsHubSectionCard`).
- The `/accounts/{id}/…` endpoints call `account_service.get_account_with_tags(..., workspace_id)` first, so a
  foreign `account_id` is already 404 there; the DAO's `([], 0)` for that case is defence in depth.

### Money: no write path depends on the changed queries

Every path that writes money finds its invoice by id, never through the changed list/summary queries:

- payments: `InvoicePaymentManager` locks `session.query(AccountInvoice).filter(id, workspace_id)` (line 62) and
  calls `update_paid_amount` (unchanged, uses `get_by_id_and_workspace`); void / delete payment use
  `get_by_id_and_workspace` (lines 261, 306, 389);
- invoice confirm / revert / void / delete / update / resync: `AccountInvoiceManager` via `get_by_id_and_workspace`,
  `update`, `remove` (BaseDAO, unchanged);
- order flows that touch invoices (purchase order manager/service, PO and SO returns, sales, expense and work
  order services): all `get_by_id_and_workspace`.

So no payment, allocation or void now silently skips an invoice. Throwaway check confirmed it:
`update_paid_amount` on an invoice whose account is in another workspace still applies (10.00 → `partial`).
The payment-picking list (`/accounts/{id}/open-invoices/`) only ever served one account of this workspace, and
an invoice of that account is unaffected by the new join.

### What the new join changes in totals

Only rows that are invalid under HR-16 (invoice `workspace_id` ≠ its account's `workspace_id`). Throwaway check
(rowkit, `bf_dao_account_invoice_test`, script in my scratchpad `se-dao-account_invoice/check_ob.py`), workspace W1
with own payables 1000.00, 300.00 (100.00 paid), 70.00 overdue, a 999.00 voided one, own receivable 250.00
(50.00 paid), plus invalid W1 invoices on a W2 account (payable 50.00, receivable 20.00 overdue) and an invalid
W2 invoice on a W1 account (5.00); old join simulated by swapping the helper:

| Read | Old join | New join |
|---|---|---|
| hub-summary payable `(open, outstanding, overdue, accounts)` | `(4, 1320.00, 1, 2)` | `(3, 1270.00, 1, 1)` |
| hub-summary receivable | `(2, 220.00, 1, 2)` | `(1, 200.00, 0, 1)` |
| `count_accounts_with_any_open_balance` | 3 | 2 |
| `summarize_invoices()` all | `(7, 1690.00, 150.00, 1540.00)` | `(5, 1620.00, 150.00, 1470.00)` |
| `summarize_invoices(account_id=W2 account)` | `(2, 70.00, 0.00, 70.00)` | `(0, 0, 0, 0)` |
| `list_invoices` count | 7 | 5 |
| `_open_balance_subquery` payable rows | own account + W2 account id | own account only |
| `_open_balance_subquery` receivable rows | own account + W2 account id | own account only |
| hub page, all three sections | unchanged | unchanged |
| own account's open-invoices total | 3 | 3 |

So: the invoices-hub KPIs now agree with the accounts-hub page (the inconsistency in the bug row). Clean data
gives identical figures. The W2 invoice on a W1 account was never counted in W1 (pinned by invoice workspace)
and still isn't.

## Downstream

No new callee. No lock, no commit. `ColumnElement` import works on the installed SQLAlchemy 2.x.

## Query shape (Postgres dialect)

- Filtered query and both hub sub-selects: `JOIN accounts ON account_invoices.account_id = accounts.id AND
  accounts.workspace_id = account_invoices.workspace_id`; outer `WHERE account_invoices.workspace_id = :ws`.
- Order-number search: `work_orders.is_deleted = false` in both the forward (`order_id IN`) and reverse
  (`id IN (SELECT invoice_id …)`) sub-selects; the purchase, expense and sales sub-selects are unchanged. OR / AND
  precedence unchanged (the `order_type = … AND order_id IN …` pairs stay grouped).
- Both name searches: `accounts.name ILIKE '%…%' ESCAPE '\'` with `\`, `%`, `_` escaped.
- Hub: `ORDER BY lower(accounts.name) ASC, accounts.id ASC` (literal `lower(accounts.name)`, ORM columns).
- Workspace bound (HR-16): every join and sub-select stays bounded by the workspace (invoice workspace pinned by the
  outer filter; order sub-selects by `workspace_id = :ws`).

## The fixer's three choices

- **(a) `hasattr(order_model, "is_deleted")`.** Not a pattern used elsewhere in `app/` (no other `hasattr`
  soft-delete check); the codebase names soft-delete columns explicitly. It is correct today (only `WorkOrder` has
  the column), stays in the loop the method already uses, and would apply HR-4 automatically if another order
  table gains the column, which is the intended rule. A mapped column attribute is always present on the class,
  so there is no false negative. Judged acceptable, **minor** for the reviewer: an explicit flag in the
  `order_specs` tuple would read more plainly. Not worth a round.
- **(b) `_same_workspace_account_join()`.** Right call: one shared helper instead of the condition copied into two
  queries, so the list/count/total paths and the hub sub-selects can't drift. Comparing with the invoice's own
  `workspace_id` instead of the parameter is equivalent (the outer filter pins it) and keeps the helper free of
  arguments. Open-balance part verified by the throwaway check above (no test of its own): foreign account ids
  drop out of both sub-selects; the hub page is unchanged, as spec R1a predicts.
- **(c) `raw.isascii() and raw.isdigit()`.** Correct: for ASCII text `isdigit()` is exactly `0-9`, so `"²"`,
  `"١٢"` and full-width digits go to the text search only, and `int()` can't raise. Trimming still happens first
  (`raw` is the stripped value). Same idea as the regex alternative; fine. (The same Unicode `isdigit` pattern in
  `app/dao/item.py` is BUG-012, another unit.)

## API contract

Value-only, see `contract.md`. No status, message, field or input change.

## Database

No constraint, index or migration: no check script required by this fix. The invalid rows stay, as the bug row
says ("the row stays for a one-off clean-up").

**Clean-up status:** detection exists: `scripts/find_cross_workspace_rows.py` builds its pairs from the models,
and `account_invoices.account_id → accounts` qualifies (both tables have `workspace_id`), so it already counts
these rows. There is **no repair script and no bug or question row** for repairing them. Proposal (not written):

1. A read-only check `scripts/bugfix/checks/account_invoice_foreign_account.py` that, per invoice workspace, lists
   the invalid invoices with `invoice_status`, `payment_status`, `invoice_amount`, `paid_amount`, outstanding,
   the number of active payments and any linked order (forward `order_type/order_id` and reverse `*.invoice_id`),
   so the owner sees how much money the hub KPIs stop counting.
2. A separate repair script, owner-approved and dry-run by default, that re-points `account_id` to the account of
   the invoice's own workspace when exactly one active account there has the same name (case-insensitive), writes
   a `financial_audit_logs` row for each change, and lists every other row for manual handling. Never run against
   production without the owner.
3. An owner question in `docs/bugfix/questions.md` (money + data repair). It does **not** block this unit: the fix
   only stops counting invalid rows; it repairs nothing. Suggested question for the orchestrator to ask: "Some old
   invoices point at a supplier/customer that belongs to another company workspace. The invoice lists and KPIs now
   leave them out. Example: Dhaka Mills' payable KPI drops from 1,050.00 to 1,000.00 because one 50.00 bill points
   at another workspace's supplier. Should such a bill be moved to the same-named supplier in Dhaka Mills, or
   voided, or handled by hand?"

## Neighbouring bugs

- BUG-637: untouched (the `if invoice_number_search:` condition and the empty-pattern result are unchanged).
- BUG-634 / BUG-635 / BUG-636 / BUG-2692: their conditions and return shapes are unchanged.
- BUG-2714 (`app/dao/expense_order.py` hub snapshots), BUG-3164 / BUG-3194 (PO / SO payment status read by invoice id),
  BUG-1801 (calendar payments): same HR-16 family in other files. Until they are fixed, the expense-order hub
  snapshot may still count an invoice that the invoices hub now leaves out. No clash.
- BUG-012 (`app/dao/item.py`, same Unicode-digit pattern): another unit.

## New bugs found (for the orchestrator to log from the owner's range)

1. `cross-workspace-row-exposed`, `app/managers/account_invoice_manager.py` (`get_invoice` and the state-changing
   methods; also `app/managers/invoice_payment_manager.py` `create_payment`) — **An invoice on another workspace's
   account is still opened, paid and voided by id.** Today: lists and totals now hide it, but
   `GET /account-invoices/{id}/` returns it with the other workspace's `account_id`, and payments, confirm, void and
   delete act on it. Intended (HR-16, per BUG-1086): treated as not found (404) on read and on every write, like a
   missing invoice; the row stays for the clean-up. Money: owner area.
2. `cross-workspace-row-exposed`, `app/services/calendar_service.py` (`_collect_invoices`) — **Calendar invoice event
   shows another workspace's account id.** Today: invoices are read by `workspace_id` only; an invoice on another
   workspace's account is shown with that `account_id` in `link` and `meta`. Intended: such an invoice gives no event
   (as BUG-1801 for payments).

## Shortcuts / scope

None. No special-cased input; the escaping reuses the file's `_escape_ilike` / `_ILIKE_ESCAPE`; nothing outside the
brief changed (docstring touch on `_build_filtered_query` only).

## Notes for the reviewer (minor)

- (a) above: `hasattr` detection vs an explicit per-kind flag.
- `_order_number_search_conditions` still has no return type hint (pre-existing, fixer noted it).
