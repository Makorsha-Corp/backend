# Fix notes: dao-account_invoice

## Round 1 (2026-11-28)

File changed: `app/dao/account_invoice.py` only (worktree `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-account_invoice`). No migration.

### Changed

- **BUG-2690**
  - New `@staticmethod _same_workspace_account_join() -> ColumnElement[bool]`: `AccountInvoice.account_id == Account.id AND Account.workspace_id == AccountInvoice.workspace_id`.
  - `_build_filtered_query` and `_open_balance_subquery` now join `Account` on that condition, not on the id alone. That covers every list, count and total the brief names: `list_invoices`, `list_invoices_page(_filtered)` (items and total), `summarize_open_hub_type`, `count_accounts_with_any_open_balance`, `summarize_invoices`, and the hub's payable and receivable sub-selects.
  - `_build_filtered_query` docstring now also mentions accounts of another workspace.
  - Import changed: `ColumnElement` added to the `sqlalchemy` import.
- **BUG-2691**: in `_order_number_search_conditions`, the per-kind filter list (`live_order_filters`) is the workspace filter, plus `is_deleted == False` when the order model has that column. Only `WorkOrder` has it. The forward subquery (`order_id`) and the reverse subquery (`invoice_id`) both use the list. Purchase, expense and sales orders are unchanged, so voided ones still match.
- **BUG-622**
  - `_build_filtered_query`: `account_name_search` now goes through `_escape_ilike` with `escape=self._ILIKE_ESCAPE`. It is still not trimmed.
  - The id shortcut now runs only when `raw.isascii() and raw.isdigit()`.
  - `list_accounts_hub_page`: `search` is escaped the same way.
- **BUG-623**: `list_accounts_hub_page` orders by `func.lower(Account.name).asc(), Account.id.asc()`. This is the convention used in `account_tag.py`, `item_tag.py` and `factory_section.py`.

### Why

- All the shared query paths go through the same join condition. So an invoice whose account is in another workspace drops out before counting and paging, everywhere at once. Same-workspace invoices always meet the extra condition, so totals for normal data stay the same. The check below confirms this.
- `_escape_ilike`, `_invoice_number_search_ilike_term`, `_outstanding_amount_expr`, `_reshape_accounts_hub_row`, `update_paid_amount`, `get_by_order` and the BaseDAO methods are unchanged. The hub still selects the 9-wide row. All signatures and return shapes are unchanged.

### Reproduction (rowkit, `bf_dao_account_invoice_test`; throwaway script in the session scratchpad, now deleted)

Setup:
- One workspace with accounts "100% Cotton", "A_B", `Back\Slash`, "BackSlash", "Zeta", "APEX" (created before "apex"), "apex", "Beta" and "seed". Each account except "seed" has one 10.00 unpaid payable.
- One more 40.00 unpaid payable in the same workspace, pointing at "Foreign Supplier", an account of a second workspace.
- Work orders:
  - live `WO-LIVE-78`, forward-linked to Zeta's invoice;
  - deleted `WO-DEL-77`, forward-linked to Beta's invoice;
  - deleted `WO-DEL-78`, reverse-linked (`invoice_id`) to apex's invoice.

| Check | Before | After |
|---|---|---|
| invoices `account_name_search="%"` | 9 accounts, foreign included | `["100% Cotton"]` |
| invoices `account_name_search="_"` | 9 accounts | `["A_B"]` |
| invoices `account_name_search="k\S"` | `["BackSlash"]` | `["Back\Slash"]` |
| hub `search="%"` / `"k\S"` | all 9 / `["BackSlash"]` | `["100% Cotton"]` / `["Back\Slash"]` |
| `invoice_number_search="²"` | `ValueError` | no error, 0 rows |
| `invoice_number_search=<id in Arabic-Indic digits>` | matched that id | no match |
| `invoice_number_search="  <id>  "` (ASCII) | matched | still matched |
| hub, search "ap" | apex(238), APEX(237): case-sensitive collation, id not the tie-break | APEX(247), apex(248): lower-name, then id |
| `list_invoices` (all) | 9, foreign invoice included | 8 |
| `account_name_search="Foreign"` | 1 | 0 |
| `list_invoices_page(account_id=foreign, open_balance_only=True)` | total 1 | `([], 0)` |
| `summarize_open_hub_type(payable)` | `(9, 120.00, 0, 9)` | `(8, 80.00, 0, 8)` |
| `count_accounts_with_any_open_balance` | 9 | 8 |
| `summarize_invoices(account_id=foreign)` | `(1, 40.00, 0.00, 40.00)` | `(0, 0, 0, 0)` |
| `summarize_invoices()` (all) | `(9, 120.00, 0.00, 120.00)` | `(8, 80.00, 0.00, 80.00)` |
| `_open_balance_subquery(payable)` rows | 9 (foreign account id included) | 8 |
| hub `section="payable"` (normal data) | 8 accounts, each 10.00 / 1 | unchanged |
| `invoice_number_search="wo-del-7"` | Beta's and apex's invoices | `[]` |
| `invoice_number_search="wo-live-78"` | Zeta's invoice | unchanged |

`ruff check app/dao/account_invoice.py`: all checks passed. `import app.main`: ok.

### Assumptions

- BUG-2691: the soft-delete filter is applied with `hasattr(order_model, "is_deleted")`, so it covers only `WorkOrder` today. If one of the other order tables gains a soft-delete column later, it would be filtered too. That fits HR-4.
- BUG-623: the test database's collation is locale-aware, so the old order was already mostly case-blind there. The visible failure was the tie-break: case-insensitively equal names were not ordered by id. On a `C`-collated database the old order would also put "apex" after "Zeta".
- The join condition compares the account's workspace with the invoice's own `workspace_id`, which the query already pins to the given workspace. That gives the same result as comparing with the parameter.

### Seen, not fixed

- `_order_number_search_conditions` has no return type hint. I left it because the line wasn't touched.

### Risk

- Totals change only for workspaces that hold cross-workspace invoice rows (invalid data under HR-16). Those rows still exist and need the one-off clean-up the brief mentions. Look at the hub KPI numbers for affected workspaces first.
