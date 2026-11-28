# Fix notes: dao-account

## Round 1 (2026-11-28)

### Changed
- `app/dao/account.py`
  - Imports: added `from sqlalchemy import exists, func`. Both are used by the new query. Nothing became unused: `AccountTag` and `AccountTagAssignment` are still used by `get_accounts_in_workspace` and by the new query.
  - `AccountDAO.get_accounts_by_tag_id` (BUG-1480, BUG-1481): I replaced the `join(AccountTagAssignment)` + `.distinct()` with a correlated `exists()` filter on `account_tag_assignments` joined to `account_tags`. The filter matches the assignment's `account_id = accounts.id`, its `workspace_id = workspace_id` and its `tag_id = tag_id`, and requires `account_tags.id = assignment.tag_id` with `account_tags.is_active = True` (BUG-1481). I added `.order_by(func.lower(Account.name).asc(), Account.id.asc())` before `.offset(skip).limit(limit)` (BUG-1480). The docstring now states the deleted-tag rule and the order. One why-comment says why it uses EXISTS instead of DISTINCT. The signature, keyword-only parameters, defaults and return type are unchanged.
- No other method was touched. There is no migration and no schema change.

### Why
- BUG-1480 (R4, HR-6): the order is lower-cased name ascending, then id ascending, written the way `app/dao/account_tag.py` and `app/dao/factory_section.py` write it. It is applied before OFFSET/LIMIT. Postgres refuses `ORDER BY lower(name)` with `SELECT DISTINCT`. EXISTS removes the need for DISTINCT, and each account still appears once.
- BUG-1481 (R3, HR-4): because the tag's `is_active` is inside the EXISTS, a deleted tag matches nothing. Hidden rows never take a place on a page (HR-5). Assignments are not changed, and the accounts come back once the tag is active again.
- R1/R2 hold: the account's own `workspace_id` and the assignment's `workspace_id` are still compared. The tag's `workspace_id` is deliberately not compared (brief §4 HR-16 note).

### Reproductions (rowkit against `bf_dao_account_test`, plus `compile_query.py`)
Setup: tag "Supplier" on active accounts "Zulu", "apple", "Banana", "apple", "Mid", and on one deleted-but-active account and one inactive account.

| Check | Before | After |
|---|---|---|
| Order (default page) | `Zulu(343), apple(344), Banana(345), apple(346), Mid(347)` (insertion/plan order) | `apple(351), apple(353), Banana(352), Mid(354), Zulu(350)` = expected |
| Pages skip 0/2/4, limit 2 concatenated = full ordered list | False | True |
| Tag set `is_active=False` | all 5 accounts returned | `[]` |
| Assignment rows after deactivating the tag | 7 | 7 (unchanged) |
| Tag re-activated | 5 | 5 |
| Other workspace | `[]` | `[]` |
| `limit=0` | `[]` | `[]` |
| `limit=-1` / `skip=-1` | DataError 2201W / 2201X | DataError 2201W / 2201X |
| Compiled SQL | `SELECT DISTINCT ... FROM accounts JOIN account_tag_assignments ... LIMIT 100 OFFSET 0`, no ORDER BY | `SELECT ... FROM accounts WHERE ... AND (EXISTS (SELECT * FROM account_tag_assignments, account_tags WHERE account_tag_assignments.account_id = accounts.id AND account_tag_assignments.workspace_id = 1 AND account_tag_assignments.tag_id = 7 AND account_tags.id = account_tag_assignments.tag_id AND account_tags.is_active = true)) ORDER BY lower(accounts.name) ASC, accounts.id ASC LIMIT 100 OFFSET 0` |

`python -c "import app.main"`: OK. `ruff check app/dao/account.py`: all checks passed. The throwaway check script (session scratchpad) has been deleted.

### Assumptions
- I used a plain `exists().where(...)` with the tag as a second FROM inside the sub-query, following `factory_section.get_by_factory`, rather than a nested EXISTS for the tag. The meaning is the same, because `account_tags.id` is the primary key.

### Seen, not fixed
- `get_accounts_in_workspace` has the same DISTINCT/no-order shape and ignores deleted tags (BUG-861/864/866/868, out of scope).
- `search_by_name_in_workspace` has no order (dead code, listed for removal elsewhere).

### Risk
- Low. This is a read-only query change. The endpoint now answers `[]` (200) for a deleted tag. The 404 comes later with BUG-2982 in the service, which was not touched.
