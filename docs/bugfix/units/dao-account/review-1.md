# Code review 1: dao-account (2026-11-28)
Verdict: PASS   (blockers: 0, majors: 0, minors: 0, nits: 1)
Diff reviewed: 092776b..43c3f76, files: app/dao/account.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

For `AccountDAO.get_accounts_by_tag_id` only:
- BUG-1481 (R3, HR-4): an account counts only if it has an assignment with
  `account_id = account.id`, the assignment's `workspace_id = workspace_id`,
  `tag_id = tag_id`, **and** that tag row has `is_active = True`. A deleted tag
  gives `[]`; nothing is written, so the assignments stay and the accounts come
  back once the tag is active again. The tag's own `workspace_id` must NOT be
  compared (R2), and nothing else of the tag row is read.
- BUG-1480 (R4, HR-6): `ORDER BY lower(name) ASC, id ASC` in SQL, before
  `OFFSET` / `LIMIT`. Because Postgres refuses `ORDER BY lower(name)` with
  `SELECT DISTINCT`, the join + `DISTINCT` must become an `EXISTS` (correlated
  on `accounts.id`), which also keeps each account once.
- Must keep: account filters (`workspace_id`, `is_active = True`,
  `is_deleted = False`; a deleted-but-active account stays hidden), filters
  before paging (HR-5), defaults 0/100, `limit=0` → `[]`, negative
  `limit`/`skip` → `DataError` 2201W/2201X, no writes/commit, signature and
  return type unchanged.
- Must not change: any other method in the file (`get_accounts_in_workspace`
  keeps its join + `DISTINCT` and its own open bugs), no service, no migration.

## 2. Findings

None at blocker, major or minor level.

Evidence gathered (throwaway checks against `bf_dao_account_test`, rolled back;
script in the reviewer's scratchpad, not in the repo):
- Compiled SQL (`scripts/bugfix/compile_query.py`): `WHERE accounts.workspace_id = 1
  AND accounts.is_active = true AND accounts.is_deleted = false AND EXISTS (SELECT *
  FROM account_tag_assignments, account_tags WHERE account_tag_assignments.account_id
  = accounts.id AND account_tag_assignments.workspace_id = 1 AND
  account_tag_assignments.tag_id = 7 AND account_tags.id = account_tag_assignments.tag_id
  AND account_tags.is_active = true) ORDER BY lower(accounts.name) ASC, accounts.id ASC
  LIMIT 100 OFFSET 0`. Correctly correlated; no tag workspace comparison;
  no DISTINCT; order before paging.
- "Zulu", "apple", "Banana", "banana" → apple, Banana(lower id), banana, Zulu. Tie
  broken by `id`.
- Inactive account, soft-deleted account, and deleted-but-`is_active=True` account
  (all tagged) are excluded and take no page place.
- `skip=1, limit=2` → Banana, banana; `skip=50` → `[]`; `limit=0` → `[]`;
  `tag_id=0` → `[]`; caller in another workspace → `[]`.
- Assignment recorded in another workspace → not counted. Assignment in this
  workspace to another workspace's tag → still counted (R2, as required).
- Tag set `is_active=False` → `[]`, all 7 assignment rows still present; tag
  reactivated → the same 4 accounts in the same order.
- 101 matching accounts: default → 100, `limit=1000` → 101 (each once).
- `limit=-1` → `DataError` 2201W "LIMIT must not be negative"; `skip=-1` →
  `DataError` 2201X "OFFSET must not be negative".
- A pending attribute change on a returned account stays pending after the call.
- `ruff check app/dao/account.py`: all checks passed.
- Only `get_accounts_by_tag_id` and the import line changed; the other methods
  are byte-identical to `origin/main`.

### Nits
- N1: `app/dao/factory_section.py:45-55` labels each part of the fixed query with
  its bug id (`# BUG-905: ...`, `# BUG-903: ...`); here the new comment explains
  the EXISTS but does not name BUG-1480 / BUG-1481. Style only.

## 3. Questions (unproven)
- No functional index on `lower(accounts.name)`; the sort is `lower(name), id`
  over one tag's accounts in one workspace. Same situation as the other HR-6
  fixes (`account_tag.py:85`, `item_tag.py:58`, `factory_section.py:57`), and
  the result set is small per tag, so not a finding.

## 4. What is good
- The `EXISTS` form matches the existing codebase pattern
  (`app/dao/factory_section.py:50`) and the sort matches `account_tag.py:85` /
  `item_tag.py:58` exactly; imports from `sqlalchemy` are the same as there.
- Fix is minimal and confined to the one method; R2's "do not compare the tag's
  workspace" is respected rather than "helpfully" tightened.
- The comment explains why EXISTS was chosen (DISTINCT + `lower()` ordering), not
  what the code does.
