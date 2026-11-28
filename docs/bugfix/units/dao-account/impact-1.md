# Impact review 1: dao-account

Date: 2026-11-28. Systems engineer, round 1. Diff: `git -C E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-account diff origin/main -- app alembic` (one file, `app/dao/account.py`, method `get_accounts_by_tag_id` plus an import line). No `alembic/` change.

**Verdict: APPROVE.**

## Change
- Join `account_tag_assignments` + `DISTINCT` replaced by a correlated `EXISTS (SELECT * FROM account_tag_assignments, account_tags WHERE assignment.account_id = accounts.id AND assignment.workspace_id = :ws AND assignment.tag_id = :tag AND account_tags.id = assignment.tag_id AND account_tags.is_active = true)` (BUG-1481).
- `ORDER BY lower(accounts.name) ASC, accounts.id ASC` before `OFFSET` / `LIMIT` (BUG-1480).
- Imports `exists, func` from `sqlalchemy`; both used. Signature, keyword-only params, defaults, return type unchanged. Docstring and one why-comment added.

## Upstream
- Only caller: `AccountService.get_accounts_by_tag_id` (`app/services/account_service.py:372`) ← `GET /accounts/by-tag/{tag_id}/` (`app/api/v1/endpoints/accounts.py:58`). Grepped `get_accounts_by_tag_id` and `account_dao` users; no manager or other service calls it.
- The service iterates the DAO list in order and builds dicts (plus one tag read per account); it does not re-sort or use a set, so the new order reaches the response unchanged.
- The service first checks the tag with the raw `account_tag_dao.get_by_id_and_workspace` (deleted tags pass). Until BUG-2982 is fixed, a deleted tag now answers **200 `[]`** (before: 200 with the tag's accounts). This is the intended DAO half of BUG-1481; BUG-2982 row already records "after BUG-1481 alone: `[]`, 200". No clash; the two fixes compose to 404.
- The service's own tag check is workspace-bound, so the "W1 assignment to a W2 tag" case (R2) can't reach the DAO through the endpoint; at DAO level it still counts because the tag's `workspace_id` is not compared (kept, as the brief requires).

## Downstream
- No locks, no writes, no commit. Pending changes untouched (read only, autoflush as before).
- `AccountTag.is_active` and `AccountTagAssignment` columns exist as used.

## Query shape (compiled, Postgres dialect)
```
... FROM accounts WHERE accounts.workspace_id = 1 AND accounts.is_active = true AND accounts.is_deleted = false
AND (EXISTS (SELECT * FROM account_tag_assignments, account_tags
  WHERE account_tag_assignments.account_id = accounts.id AND account_tag_assignments.workspace_id = 1
  AND account_tag_assignments.tag_id = 7 AND account_tags.id = account_tag_assignments.tag_id
  AND account_tags.is_active = true))
ORDER BY lower(accounts.name) ASC, accounts.id ASC LIMIT 100 OFFSET 0
```
- Correlation is correct: `accounts` is not repeated in the sub-query's FROM.
- Only one `ORDER BY` (outer); it uses ORM columns, no `DESC`, no `text()`, no labels. The text between the first `ORDER BY` and `LIMIT` is `lower(accounts.name) ASC, accounts.id ASC`.
- No `DISTINCT` needed: EXISTS yields each account once (also `uq_account_tag` on `(account_id, tag_id)`).
- The tag's `workspace_id` is not compared (R2 kept).

## Index use (EXPLAIN on `bf_dao_account_test`, `enable_seqscan = off`)
`Limit → Sort (lower(name), id) → Nested Loop Semi Join`; inner side uses `ix_account_tag_assignments_account_id` (filter ws, tag) and `ix_account_tags_id` (Index Cond `id = 7`, filter `is_active`). The EXISTS plans as a semi-join and the existing single-column indexes (`account_id`, `tag_id`, `workspace_id`, `uq_account_tag`) serve it; no new index needed. The sort on `lower(name)` has no expression index, same as every other HR-6 list in the codebase; result sets are per-tag and small. Not a finding.

## Workspace bound (HR-16)
Account `workspace_id` and assignment `workspace_id` both still compared. Tag row reached only through the assignment's `tag_id` = the given `tag_id`. No new unbounded join.

## API contract
Value change only, no shape/status change: see `contract.md`. Frontend (`../frontend/src`) has no caller of `/accounts/by-tag/` (grep `by-tag|byTag|by_tag`: none), so the frontend stage is skipped.

## Database
No migration, constraint or index. No check script needed.

## Neighbouring bugs
- BUG-2982 (service 404 for a deleted tag): composes cleanly, see above. Its strict xfail stays failing after this fix (expected; not this unit).
- BUG-861/864/866/868 (`get_accounts_in_workspace`, same file): untouched, as the brief requires. Same DISTINCT/order shape; a later dao-account unit should fix them (tester precheck note).
- BUG-1486 (assignment DAO tag order): unaffected.

## Shortcuts / scope
None. No special-cased input; the deleted-tag rule is in the query, before paging (HR-5). Nothing changed beyond the one method and its import.

## Throwaway verification (for the tester, not the fixer)
With the worktree's `app` on the path (verified by printing the module file): `tests/unit/dao/test_account.py`, `tests/unit/services/test_account_service.py`, `tests/unit/managers/test_account_manager.py` → 242 passed, 148 xfailed; the only changes are ACC-BT-07 and ACC-BT-09 XPASS(strict) and ACC-BT-08 XPASS (non-strict), i.e. exactly BUG-1481/BUG-1480. With `--runxfail -k "acc_bt or asv_t"`: 28 passed, 1 failed (ASV-T-07, BUG-2982, expected). ACC-BT-19 (W2 tag still counts) passes.

## New bugs found
None.

## Notes for docs/future
None.
