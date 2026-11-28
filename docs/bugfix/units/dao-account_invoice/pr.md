## Fix: invoice searches take `%` and `_` literally, the accounts hub sorts names A to Z whatever the case, and invoices on another workspace's account no longer show up in lists and totals

**Fixes BUG-622, BUG-623, BUG-2690 and BUG-2691.** One file (`app/dao/account_invoice.py`). No database change, no API shape change (values only), no frontend change.

---

### What was wrong

**1. Invoices pointing at another workspace's supplier or customer were listed and counted (BUG-2690). This is the one that matters most: it touches the invoice KPIs.**

An invoice belongs to a workspace, and it points at an account (a supplier or a customer). Some old rows point at an account of a *different* workspace. That is invalid data (house rule HR-16: links across workspaces are never allowed). The invoice lists, the account-name search and the invoices-hub totals still joined those accounts, so the foreign supplier's name appeared in this workspace and its bills were added to the KPIs. The accounts hub page already left them out, so the two pages disagreed.

*Example:* Dhaka Mills has a 1,000.00 taka bill on its own supplier and a 50.00 taka bill that points at another workspace's supplier. The invoices hub showed the payable KPI as **"2 open, 1,050.00 taka, 2 accounts"**, while the accounts hub showed one supplier owing 1,000.00.

**2. `%` and `_` in an account-name search matched everything (BUG-622)**

The account-name search on the invoice list and the accounts-hub search box passed the text straight into a database pattern, where `%` and `_` are wildcards and `\` is special.

*Example:* accounts "100% Cotton" and "Cotton Mills". Searching `%` returned both, and every other account too.

The invoice-number search had a related problem: when the text looked like a number it also matched the invoice id, but "looks like a number" accepted any Unicode digit. Typing `²` crashed the request with a server error, and Arabic-Indic digits `١٢` matched invoice 12.

**3. A deleted work order's number still found its invoice (BUG-2691)**

Searching invoices by order number also looks at the linked work order's number, including deleted work orders.

*Example:* work order `WO-DEL-77` was deleted. Searching `wo-del-7` still returned its invoice. (The invoice itself is still found by its own invoice number.)

**4. The accounts hub sorted upper-case names before lower-case ones (BUG-623)**

*Example:* "APEX", "Zeta", "Beta", "apex" came back as APEX, Beta, Zeta, apex. Now: APEX, apex, Beta, Zeta. Names that differ only in case stay in creation order.

---

### What changed

All in `app/dao/account_invoice.py`:

```diff
+ def _same_workspace_account_join():             # one shared join for lists, counts, totals and hub balances
+     return and_(AccountInvoice.account_id == Account.id,
+                 Account.workspace_id == AccountInvoice.workspace_id)   # HR-16: same workspace only

- .join(Account, AccountInvoice.account_id == Account.id)
+ .join(Account, self._same_workspace_account_join())      # in the invoice list query and the hub balance sub-query

- if raw.isdigit():
+ if raw.isascii() and raw.isdigit():               # id shortcut only for plain 0-9

- Account.name.ilike(f"%{account_name_search}%")
+ Account.name.ilike(f"%{self._escape_ilike(account_name_search)}%", escape="\\")   # HR-8: % _ \ are literal
- Account.name.ilike(f"%{search}%")
+ Account.name.ilike(f"%{self._escape_ilike(search)}%", escape="\\")                # same for the hub search

+ if hasattr(order_model, "is_deleted"):            # only work orders are soft-deletable
+     live_order_filters.append(order_model.is_deleted == False)   # HR-4: deleted orders don't match

- .order_by(Account.name.asc(), Account.id.asc())
+ .order_by(func.lower(Account.name).asc(), Account.id.asc())     # HR-6: name ignoring case, then id
```

The escaping reuses the helper this file already uses for the invoice-number search.

### What you'll notice

- **Invoice totals and KPIs change only in workspaces that hold invoices on another workspace's account.** Those invoices are now left out of the invoice list, the account-name search, the invoices-hub KPIs, "accounts with an open balance" and the per-account invoice summary. In the example above, Dhaka Mills' payable KPI goes from **"2 open, 1,050.00 taka, 2 accounts"** to **"1 open, 1,000.00 taka, 1 account"**, which now matches the accounts hub page. **Nothing is repaired:** the rows stay in the database, untouched, for a later clean-up. Workspaces with clean data see exactly the same figures as before.
- Paying, confirming, voiding or deleting an invoice is unchanged: those find the invoice by its id, not through these lists.
- `%`, `_` and `\` in the account-name and hub searches find only names that contain them.
- `²` in the invoice-number search no longer gives an error; non-ASCII digits are searched as text only.
- A deleted work order's number no longer finds the invoice linked to it.
- The accounts hub lists names A to Z ignoring case; equal names keep creation order.
- Deliberately unchanged: a search made only of spaces (BUG-637, below).

### What to look at when reviewing

- **Invalid invoices are hidden, not fixed.** This PR only stops counting them. How to repair them (move each to the same-named account in its own workspace, void it, or handle by hand) is a money and data decision for the owner, proposed separately with a read-only check first. Object if you'd rather the KPIs keep counting them until the repair is done.
- **Hidden in lists, still reachable by id.** Opening, paying or voiding such an invoice by its id still works today. Treating it as "not found" there too belongs to the invoice manager and payment manager, a separate fix in other files.
- **BUG-637 is left for a later unit.** A search of only spaces should mean "no filter", but the fix needs both this file and `app/dao/account.py` (account search). It will be done as one two-file unit later so both searches change together.
- **How deleted orders are detected.** The code checks whether the order table has an `is_deleted` column (today only work orders do), rather than naming work orders explicitly. A per-order-type flag would read more plainly; say so if you prefer it.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the changed queries are reached only through `AccountInvoiceManager` (invoice list, hub summary, accounts hub page, account invoice summary / open invoices / invoices), all read-only. No money write path uses them; payments, confirm, void and delete look invoices up by id. No caller re-sorts. A throwaway check with mixed valid and invalid rows confirmed only the invalid rows drop out of the totals.
- **Contract:** same shape, codes, messages and inputs; values only (see the list above). The frontend shows server values and order as returned, so no frontend PR.
- **Tests:** the 30 tests marked as known failures for these four bugs (invoice DAO and invoice manager) now pass, and their markers are removed. Every other test in the full suite had the same result before and after, apart from 33 order-tie tests elsewhere that pass or fail by luck and are ignored (flip check CLEAN, base `092776b`). The BUG-637 tests are still known failures, as expected.
- **Database:** no migration; Alembic unchanged.
- **Follow-ups for the orchestrator** (in the impact review): two new HR-16 bugs (invoice opened/paid by id; calendar invoice events) and a clean-up proposal for the invalid rows.
- **Commits:** `698188f` on branch `bugfix/dao-account_invoice`.

</details>

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 0 minors, 2 nits (strict independent review, `review-1.md`).

Nits: the deleted-work-order filter is chosen with `hasattr(order_model, "is_deleted")` rather than declared per order kind (correct today, since only work orders have the column); the helper `_same_workspace_account_join` returns a join condition, so `..._join_condition` would be a clearer name.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
