# Tester pre-check: dao-account

Date: 2026-11-28. Unit `dao-account`, `app/dao/account.py`, bugs BUG-1480, BUG-1481.
Run: `TEST_DATABASE_URL=…/bf_dao_account_test`, `-k "acc_bt or asv_t" --runxfail -rf` over
`tests/unit/dao/test_account.py` and `tests/unit/services/test_account_service.py`: 4 failed, 25 passed
(the 3 targets below plus ASV-T-07, which is BUG-2982's, not this unit's).

**Verdict: no wrong tests.** Both bugs go ahead. `wrong-tests.md` untouched.

## How the tests were found
- Markers: constants `BUG_1480`, `BUG_1481` in `tests/unit/dao/test_account.py` (lines 41–42), used only by the three markers below.
- Callers of `account_dao.get_accounts_by_tag_id`: only `AccountService.get_accounts_by_tag_id`. Its tests (`tests/unit/services/test_account_service.py`, ASV-T-01…10) carry no BUG-1480 / BUG-1481 marker. No manager or API test calls this method.

## BUG-1480 (order)
| Test | Strict | Fails today on | Verdict |
|---|---|---|---|
| ACC-BT-08 `test_acc_bt_08__ordered_by_name_case_insensitive_then_id` (dao) | non-strict | Then 2, line 1056: `['Zulu', 'apple', 'Banana']` vs `['apple', 'Banana', 'Zulu']` | right. Names chosen so the intended order differs from `id` order both ways; seqscan + update of "apple" pushes it to the physical end. Checks R4 and nothing more. |
| ACC-BT-09 `test_acc_bt_09__the_query_orders_by_name_case_insensitive_then_id` (dao) | strict | Then 2, line 1076: no `ORDER BY` in the SQL | right, with a **SQL-text risk** (below). |

**SQL-text risk for the systems engineer (BT-09):** the ORDER BY part (text between the first `ORDER BY` and the next `LIMIT`) must contain `lower(accounts.name)` and `accounts.id`, and no `DESC`. A normal ORM fix (`func.lower(Account.name).asc(), Account.id.asc()`, the convention in `account_tag.py` / `item_tag.py`) passes. It would fail if the fix used a raw `text()` sort, a labelled/aliased column, `ilike`/collation tricks, or put an `ORDER BY` inside the `EXISTS` sub-query (the split takes the first `ORDER BY`). Keeping `DISTINCT` and adding `lower(name)` is refused by Postgres (42P10), hence the row's `EXISTS` instruction.

## BUG-1481 (deleted tag)
| Test | Strict | Fails today on | Verdict |
|---|---|---|---|
| ACC-BT-07 `test_acc_bt_07__a_deleted_tag_gives_an_empty_list_its_links_stay` (dao) | strict | Then 2, line 1033: `[A1]` vs `[]` (Then 1, the link still exists, holds today) | right. Checks exactly R3 (empty list, assignment untouched). |

**Service part of the row (FU-1 (a), 404 for a deleted tag):** decided **out of this unit**. It is its own row, BUG-2982 (`app/services/account_service.py`), with its own strict test ASV-T-07 tagged `BUG_2982` only. After this DAO fix the service returns `[]` instead of raising, so ASV-T-07 still fails with "DID NOT RAISE NotFoundError" and stays a strict xfail: the flip check sees no change there. No test tagged BUG-1481 checks the 404, so the row/test split is clean; the DAO part of BUG-1481's Intended is fully reachable in one file.

## Constraints a correct fix must keep (passing tests today)
- **ACC-BT-19** (R2): a W1 assignment to a **W2 tag** still counts — the tag's own `workspace_id` must not be compared. A fixer "tightening" HR-16 by adding `AccountTag.workspace_id == workspace_id` would break it. The brief states this as a fact of R2.
- ACC-BT-01…06, 10–18: account active / not deleted, account and assignment workspace, default limit 100, `limit=1000` gives 101 each once, `limit=0`, negative limit/skip `DataError` 2201W / 2201X, filter-before-paging, no write and pending changes kept.
- ASV-T-01…10 (service): set comparisons and paging pass-through; none depends on order or on a deleted tag listing accounts.

## Outside this unit
- `get_accounts_in_workspace` in the same file has the same `DISTINCT` + missing `ORDER BY` shape (BUG-866, with BUG-864 deleted-tag join, BUG-861, BUG-868). Those rows are filed under `app/managers/account_manager.py` "(via `app/dao/account.py`)", but the fix lands in this DAO file; its strict SQL check ACC-IW-28 has the same `lower(accounts.name)` text risk. The next planner should plan them as a later `dao-account` unit (or name the DAO with "fix in") rather than as a manager unit.
- BUG-2982 (service 404 for a deleted tag) can go in any later batch; it does not depend on this fix being merged first, but after both, a deleted tag answers 404.
