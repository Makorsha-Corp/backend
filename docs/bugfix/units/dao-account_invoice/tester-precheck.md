# Tester pre-check: dao-account_invoice

Date: 2026-11-28. Base: main checkout at 181c48a (`app/dao/account_invoice.py` identical to `origin/main`).
Database: `bf_dao_account_invoice_test`. Run: `--runxfail --tb=line -o addopts=""` on the target tests only.

**Verdict: all 30 target tests (BUG-622 15, BUG-623 4, BUG-2690 9, BUG-2691 2) are right and all fail today as their cards say. No wrong tests.** Flip check for this unit: `--bugs BUG-622,BUG-623,BUG-2690,BUG-2691`. One scope change: BUG-637 is taken out of this unit (see "BUG-637" below).

## How the tests were found

- Bare-number grep of `622|623|637|2690|2691` over `tests/**/*.py`.
- DAO file uses constants `R622`, `R623`, `R637`, `R2690`, `R2691` (`tests/unit/dao/test_account_invoice.py` lines 78–90); every `xfail(... reason=R…)` use mapped.
- Callers: `AccountInvoiceManager` is the only caller of the list / summary / hub methods; its tests (`tests/unit/managers/test_account_invoice_manager.py`) use literal reasons. No `tests/unit/services` test names these bugs.
- No target test names a second bug; no combined reasons.

## BUG-622 (HR-8 escaping, ASCII-only id shortcut) — 15 tests, all right

| Test | Rule | Fails today on |
|---|---|---|
| dao `test_aiv_fq_36__superscript_digit_searched_as_text` | `_build_filtered_query` R10 | `ValueError` at `app/dao/account_invoice.py:129` (`int("²")`) — as the card says |
| dao `test_aiv_fq_37__arabic_indic_digits_do_not_match_id` | R10 | Arabic-Indic id matches (1 row, expected `[]`) |
| dao `test_aiv_fq_40__percent_in_account_name_search_literal` | R11 | `%` matches both accounts |
| dao `test_aiv_fq_41__underscore_in_account_name_search_literal` | R11 | `_` matches both accounts |
| dao `test_aiv_fq_42__backslash_in_account_name_search_literal` | R11 | `k\S` finds `BackSlash`, not `Back\Slash` |
| dao `test_aiv_ah_20__percent_in_hub_search_literal` | `list_accounts_hub_page` R4 | `%` matches both |
| dao `test_aiv_ah_21__underscore_in_hub_search_literal` | R4 | `_` matches both |
| dao `test_aiv_ah_22__backslash_in_hub_search_literal` | R4 | wrong account |
| mgr `test_l_33__superscript_digit_no_crash` | manager `list_invoices` R10 | `ValueError` at :129 |
| mgr `test_l_34__arabic_indic_digits_should_not_match_id` | R10 | id match |
| mgr `test_l_36__account_name_percent_literal` | R11 | matches every account |
| mgr `test_l_37__account_name_underscore_literal` | R11 | matches every account |
| mgr `test_l_38__account_name_backslash_literal` | R11 | lone `\` becomes `%\%` (escaped `%`), finds nothing |
| mgr `test_ah_09__percent_literal` | manager hub R4 | matches every account |
| mgr `test_ah_10__underscore_literal` | manager hub R4 | matches every account |

Judgement: each checks exactly the row's "Intended" (literal `%`, `_`, `\`; ASCII-only shortcut; never raises) and nothing more. A correct fix (reuse `_escape_ilike` + `escape="\\"`; check `raw` against ASCII `0-9` only, e.g. `raw.isascii() and raw.isdigit()` or a regex) passes them all. Passing companions that must stay green: AIV-FQ-35 / AIM-L-30, L-31, L-32 (ASCII id shortcut, trimmed, `12x` no match), AIV-FQ-38 / FQ-39 (account search not trimmed) — the brief states these.

## BUG-623 (case-insensitive hub order) — 4 tests, all right

| Test | Rule | Fails today on |
|---|---|---|
| dao `test_aiv_ah_25__case_only_names_case_insensitive_then_id` | `list_accounts_hub_page` R5 | `[b2, b1, b3]` (collation order) instead of id order |
| dao `test_aiv_ah_26__hub_query_orders_by_lower_name` | R5 | Then 2: `lower(accounts.name)` not in the ORDER BY |
| mgr `test_ah_15__case_insensitive_name_order` | manager hub R6 | APEX/apex not adjacent |
| mgr `test_ah_22__case_insensitive_equal_names_tie_break_by_id` | R6 | `acme`/`Acme` by collation |

**SQL-text risk for the systems engineer:** AIV-AH-26 requires the literal `lower(accounts.name)` in the ORDER BY. `func.lower(Account.name)` (the codebase convention, pointed to in the brief) produces it; a `collate(...)`, `ilike`-based or raw `text()` sort would fail it even if the order were right.

## BUG-2690 (HR-16 cross-workspace account) — 9 tests, all right

| Test | Rule | Fails today on |
|---|---|---|
| dao `test_aiv_fq_06__invoice_on_w2_account_not_listed` | `_build_filtered_query` R2a | Then 2: foreign-account invoice listed |
| dao `test_aiv_fq_07__invoice_on_w0_account_not_listed` | R2a | Then 2 (lower-id workspace's account) |
| dao `test_aiv_fq_08__foreign_account_name_does_not_find` | R2a, R11 | foreign name matches |
| dao `test_aiv_lp_09__w1_invoice_on_w2_account_not_listed` | `list_invoices_page` R1 | listed under foreign account id |
| dao `test_aiv_pf_17__invoice_on_w0_account_neither_listed_nor_counted` | `list_invoices_page_filtered` R1, R2 | Then 2: total 2 |
| dao `test_aiv_hs_10__invoice_on_w2_account_not_counted` | `summarize_open_hub_type` R1 | `(2, 50.00, 0, 2)` vs `(1, 10.00, 0, 1)` |
| dao `test_aiv_hs_11__invoice_on_w0_account_not_counted` | R1 | same |
| dao `test_aiv_ca_07__invoice_on_w2_account_does_not_count` | `count_accounts_with_any_open_balance` R1 | 2 vs 1 |
| dao `test_aiv_si_09__invoice_on_w2_account_not_summed` | `summarize_invoices` R1 | `(1, 100.00, …)` vs zeros |

(The row's `_open_balance_subquery` R1a has no observable effect on the hub page — spec says so — so it has no test of its own. The systems engineer should check the fixer changes the subquery join too, by reading the diff.)

Judgement: build invalid data on purpose (per the spec's 2026-11-10/11 note) and check it never leaks into lists, counts or totals. They depend on no other bug: `summarize_open_hub_type` expected values (overdue 0, drafts counted the default way) are today's for BUG-634/635, which stay unfixed; `summarize_invoices` checks only `result[:4]`, which also survives a later BUG-2692 shape change. A correct fix (join `Account.id == AccountInvoice.account_id AND Account.workspace_id == AccountInvoice.workspace_id`) passes all.

## BUG-2691 (deleted work order in number search) — 2 tests, all right

| Test | Rule | Fails today on |
|---|---|---|
| dao `test_aiv_on_14__deleted_wo_number_does_not_find_forward` | `_order_number_search_conditions` R4 | forward link matches |
| dao `test_aiv_on_15__deleted_wo_number_does_not_find_reverse` | R4 | reverse link matches |

Passing companion AIV-ON-16 (invoice of a deleted WO still found by its own number) guards against over-hiding. A correct fix adds `WorkOrder.is_deleted == False` to both work-order sub-selects only.

## BUG-637 — taken out of this unit (not a wrong test)

Target tests that carry the BUG-637 tag:

| Test | File / module | Rule |
|---|---|---|
| `test_aiv_fq_33__whitespace_only_number_search_no_filter` | `app/dao/account_invoice.py` | `_build_filtered_query` R9a |
| `test_l_29__whitespace_search_should_be_no_filter` | account invoice manager → this DAO | manager `list_invoices` R9a |
| `test_acc_iw_08__…`, `test_acc_iw_09__…`, `test_acc_iw_43__…` (`tests/unit/dao/test_account.py`) | **`app/dao/account.py`** `get_accounts_in_workspace` R2 | account DAO spec P1: "BUG-637 (existing) … The fix is in this file" |
| `test_acc_s_05__…`, `test_acc_s_11__…` (`tests/unit/managers/test_account_manager.py`) | **`app/dao/account.py`** via `AccountManager.search_accounts` R2/R5 | account manager spec P6 |

All 7 fail today as their cards say and all check the right behaviour. But the real scope of BUG-637 is two files (`app/dao/account_invoice.py` and `app/dao/account.py`), although its row names only the first. The flip check treats every test whose reason names BUG-637 as a target, so a fix of the invoice file alone would leave 5 targets xfailed and be **rejected**. `app/dao/account.py` is the `dao-account` unit's file in this same batch, so it can't join this unit (planner §1: no shared files in a batch; a bug naming two files is planned later as a two-file unit).

Action: BUG-637 removed from this unit's brief (the fixer is told to leave whitespace-only search as it is) and from the `state.md` row. **Next planner:** plan BUG-637 as a two-file unit (`app/dao/account_invoice.py` + `app/dao/account.py`) once neither file has an open unit. Suggest also correcting the BUG-637 row's Module column to name both files.

## Outside this unit

- **dao-account unit (same batch):** `tests/unit/dao/test_account.py` and `tests/unit/managers/test_account_manager.py` hold 5 BUG-637 xfails (above). They are not that unit's targets (BUG-1480/1481) and must stay xfailed after its fix; its tester must not remove them.
- The `dao-account` and this unit must not both be given BUG-637 in `--bugs`.
- No other caller pattern found: `app/managers/account_invoice_manager.py` forwards every list/summary call unchanged; nothing else builds its own invoice-account join.
