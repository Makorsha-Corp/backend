# Code review 1: dao-account_invoice (2026-11-28)
Verdict: PASS   (blockers: 0, majors: 0, minors: 0, nits: 2)
Diff reviewed: 092776b..698188f (merge-base origin/main .. bugfix/dao-account_invoice), files: app/dao/account_invoice.py (+30 / -10). No alembic changes.

## 1. What a correct fix must do (written before reading the diff)

- **BUG-622 (HR-8).**
  - `account_name_search` in `_build_filtered_query` and `search` in `list_accounts_hub_page` must use the file's own `_escape_ilike` plus `escape=_ILIKE_ESCAPE`, inside `%…%`, and must **not** be trimmed. `%` finds only names containing `%`, `_` only names containing `_`, `k\S` finds `Back\Slash` but not `BackSlash`, and a lone `\` finds only names with a backslash.
  - The id shortcut must fire only for trimmed text made of ASCII `0-9`. `"²"` must not raise, `"١٢"` must not match an id, `"  12  "` must still match id 12, and `"12x"` must not use the shortcut.
  - `_escape_ilike` and `_invoice_number_search_ilike_term` must stay the same. The whitespace-only search behaviour (BUG-637) must not change.
- **BUG-623 (HR-6).** The hub page must sort by `lower(name)` ascending, then `id` ascending (the convention in `app/dao/account_tag.py:85`). `count()` and the paging must be otherwise unchanged.
- **BUG-2690 (HR-16).**
  - The account join in **both** `_build_filtered_query` and `_open_balance_subquery` must require the account's workspace to equal the invoice's workspace, in SQL, before paging and aggregation.
  - That covers every caller: `list_invoices`, the page methods, `summarize_open_hub_type`, `count_accounts_with_any_open_balance` and `summarize_invoices`.
  - Passing a foreign `account_id` must give an empty result with total 0.
  - The 9-wide hub row and the 4-value summary must keep their shape.
- **BUG-2691 (HR-4).**
  - In `_order_number_search_conditions`, a work order with `is_deleted = True` must match through neither the forward link (`order_type`/`order_id`) nor the reverse link (`invoice_id`).
  - Purchase, expense and sales orders must be unaffected, so a voided PO still matches.
  - The invoice must still be found by its own numbers.
- **Must not change:** the open-balance conditions (BUG-634/635/636), `update_paid_amount`, `get_by_order`, the inherited `BaseDAO` methods, any signature or default, and the return shapes.

## 2. Findings

None at blocker, major or minor level.

Evidence gathered. A throwaway check ran through `scripts/bugfix/rowkit.py` against `bf_dao_account_invoice_test`, inside a transaction that was rolled back. The script is `C:\Users\User\AppData\Local\Temp\claude\5703096e36d5cd6b\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\review-dao-account_invoice\check.py`.

- **BUG-2690.**
  - Setup: the workspace's own account has a 1,000.00 payable, and the workspace also has a 50.00 payable on another workspace's account.
  - `list_invoices` returns only the own invoice.
  - `summarize_open_hub_type(payable)` returns `(1, 1000.00, 0, 1)`.
  - `count_accounts_with_any_open_balance` returns `1`.
  - `summarize_invoices(account_id=foreign)` returns `(0, Decimal('0'), Decimal('0'), Decimal('0'))`.
  - `list_invoices_page(account_id=foreign, open_balance_only=True)` returns `([], 0)`.
  - `account_name_search="Foreign"` returns `[]`.
- **BUG-622, name searches.** In both the invoice list and the hub:
  - `%` finds only "100% Cotton".
  - `_` finds only "A_B".
  - `k\S` and a lone `\` find only `Back\Slash`, not `BackSlash`.
  - `" cotton"` finds "100% Cotton", so the text is not trimmed.
- **BUG-622, id shortcut.**
  - `"²"` and `"١٢"` give `[]` and do not raise.
  - `"  <id>  "` returns that invoice; `"<id>x"` returns `[]`.
  - `"99999999999999999999"` gives `[]` and does not raise.
- **BUG-2691.**
  - Searching `wo-del-7` matches neither the forward-linked nor the reverse-linked invoice of deleted work orders.
  - A live work order still matches.
  - The invoice of a deleted work order is still found by its own `invoice_number`.
  - A PO with status `voided` still matches.
- **BUG-623.**
  - Names "APEX", "Zeta", "Beta", "apex", "acme", "Acme", "acme" come out as acme(1654), Acme(1655), acme(1656), APEX(1650), apex(1653), Beta, Zeta. That is case-insensitive order with `id` breaking ties.
  - The total stays at 7 on the last page and past the end.
- **Static checks.**
  - `ruff check app/dao/account_invoice.py` passes.
  - `ColumnElement` is a valid top-level import in the installed SQLAlchemy 2.0.51.
  - Only `WorkOrder` has `is_deleted` among the four order models (`app/models/work_order.py:96`, NOT NULL, default False), so the `hasattr` guard selects exactly the work-order spec.
  - `== False` matches the file's existing style (line 117).
  - The `ORDER BY lower(name), id` matches `app/dao/account_tag.py:85`.
  - The escaping reuses the file's own helper, as `app/dao/help_ticket.py:147-152` does.

### Nits
- N1. `app/dao/account_invoice.py:68`: the soft-delete filter is chosen by `hasattr(order_model, "is_deleted")` rather than declared in `order_specs`. It is correct today, but it is implicit. A flag in each spec tuple would make the HR-4 rule visible next to the order kinds.
- N2. `app/dao/account_invoice.py:43`: `_same_workspace_account_join` returns an ON condition, not a join. `_same_workspace_account_on` or `..._join_condition` would describe it better.

## 3. Questions (unproven)
- None that block. There is no functional index on `lower(accounts.name)`, but the hub query is bounded to one workspace's accounts and `account_tag` uses the same unindexed pattern, so this is not raised as a finding.

## 4. What is good
- The root cause is fixed once, in a shared ON-clause helper used by both account joins. All five aggregate and list callers are covered in SQL before paging, with no Python-side filtering.
- The escaping reuses the file's existing `_escape_ilike` / `_ILIKE_ESCAPE` instead of adding a third copy.
- The live-order filter is applied identically to the forward and reverse subqueries.
- The diff is minimal. No out-of-scope conditions (BUG-634/635/636/637) changed, and the signatures and return shapes are unchanged.
- The comments explain why (ASCII-only digits; voided is a state, not a deletion).
