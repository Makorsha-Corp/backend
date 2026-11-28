# Contract note: dao-account_invoice

Date: 2026-11-28. Endpoints: `GET /account-invoices/`, `GET /account-invoices/hub-summary/`, `GET /accounts/hub/`,
`GET /accounts/{id}/invoice-summary/`, `GET /accounts/{id}/open-invoices/`, `GET /accounts/{id}/invoices/`.

No change to response shape, status codes, error messages or inputs. Value changes only:

1. **Account-name search is literal** (`account_name_search` on `GET /account-invoices/`, `search` on
   `GET /accounts/hub/`): `%`, `_` and `\` match themselves. Example: accounts "100% Cotton" and "Cotton Mills";
   searching `%` now returns only "100% Cotton" (before: both, and every other account).
2. **Invoice-number search, id shortcut:** only plain digits `0-9` also match the invoice id. `"²"` no longer gives a
   500; Arabic-Indic digits `"١٢"` no longer match invoice 12 (they are searched as text).
3. **Invoice-number search ignores deleted work orders:** a deleted work order's number no longer finds the invoice
   linked to it. Example: `WO-DEL-77` deleted; searching `wo-del-7` no longer returns its invoice. The invoice is still
   found by its own number.
4. **Accounts hub order:** by name ignoring case, then id. Example: "APEX" (1), "Zeta" (2), "Beta" (3), "apex" (4) →
   APEX, apex, Beta, Zeta.
5. **Invoices on another workspace's account (invalid old data) are left out** of every list, count and total above.
   Example: Dhaka Mills has a 1,000.00 bill on its own supplier and a 50.00 bill pointing at another workspace's
   supplier; the payable KPI goes from "2 open, 1,050.00, 2 accounts" to "1 open, 1,000.00, 1 account", now matching
   the accounts hub page. Clean data gives the same figures as before.

Frontend: the web app sends the same parameters and shows the values as returned, with no client-side sort or
special-casing of these searches (`features/accountInvoices/accountInvoicesApi.ts`, `features/accounts/accountsApi.ts`,
`pages/newpages/AccountsLandingPage.tsx`). **No frontend change; the frontend stage is skipped.**
