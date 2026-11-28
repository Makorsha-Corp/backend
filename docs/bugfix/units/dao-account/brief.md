# Fix brief: dao-account

## 1. Unit

| | |
|---|---|
| Slug | `dao-account` |
| Source file | `app/dao/account.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-account` |
| Branch | `bugfix/dao-account` (from `origin/main`) |
| Risk | `normal` (BUG-1480 `unordered-pagination` is on the trivial list; BUG-1481 `join-ignores-soft-deleted` is not) |

Only **one method** is in this unit: `AccountDAO.get_accounts_by_tag_id`. The other methods of the file carry other open bugs that are not part of this unit (see §6); leave them exactly as they are.

## 2. Bugs

### BUG-1480: Accounts of one tag have no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `app/dao/account.py` (`get_accounts_by_tag_id`; reached through `GET /accounts/by-tag/{tag_id}/`).
- **Today:** No `ORDER BY` (`SELECT DISTINCT … LIMIT … OFFSET`); the order follows the query plan, so pages can repeat or skip accounts.
- **Intended:** HR-6: name case-insensitive ascending, then `id` ascending, before `skip` / `limit` (same order as BUG-866). Postgres refuses `ORDER BY lower(name)` with `SELECT DISTINCT` (42P10, "for SELECT DISTINCT, ORDER BY expressions must appear in select list"): use `EXISTS` instead of join + `DISTINCT`.
- **Example:** Tag "Supplier" is on "Zulu", "apple" and "Banana". The list comes back "apple", "Banana", "Zulu" (case ignored), and two accounts with the same name come back lower `id` first. Today the order is whatever the plan gives, and it changed after an account was updated.

### BUG-1481: "Accounts with tag N" lists the accounts of a deleted tag
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `app/dao/account.py` (`get_accounts_by_tag_id`; reached through `GET /accounts/by-tag/{tag_id}/`).
- **Today:** The tag row is not read; the accounts of a tag with `is_active = False` are returned.
- **Intended:** HR-4 (per BUG-864): a deleted tag matches nothing, `[]`; assignments untouched, listed again once the tag is active.
- **Not in this unit:** the bug row adds that the account *service* should answer 404 for a deleted tag. That is BUG-2982, a separate row in `app/services/account_service.py`, and is out of scope here (§6). After this fix the endpoint answers `[]` (200) for a deleted tag; the 404 comes with BUG-2982 later. Do not touch the service.
- **Example:** Tag 7 "Old supplier" is deleted (`is_active = False`) while "Acme Ltd" still carries it. "Accounts with tag 7" today lists Acme Ltd; after the fix it lists nothing. The assignment row stays; if tag 7 is made active again, Acme Ltd is listed again.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `accounts`; account soft delete is `is_deleted = True` (the manager also sets `is_active = False`); a row with `is_deleted = True, is_active = True` is possible and is treated as deleted by every method here. For account tags, "deleted" is `account_tags.is_active = False` (there is no `is_deleted` on tags). `account_tag_assignments` is unique on `(account_id, tag_id)` (`uq_account_tag`), across workspaces, so one account has at most one assignment to a given tag. `account_tags.tag_code` has no unique index. Every parameter after `db` is keyword-only. The DAO validates nothing, writes nothing of its own and never commits.

### `AccountDAO.get_accounts_by_tag_id(db, *, workspace_id, tag_id, skip=0, limit=100)`
Used by `AccountService.get_accounts_by_tag_id` ← `GET /accounts/by-tag/{tag_id}/`, after the service has checked that the tag exists in the workspace (the endpoint pages, `limit` up to 100). Returns a `list` of `Account` (possibly empty). Purpose: one page of the live, active accounts that carry one tag.

- **R1.** Returns accounts of `workspace_id` with `is_active = True`, `is_deleted = False` and an assignment to `tag_id` recorded in `workspace_id` (the assignment's own `workspace_id`). Inactive and soft-deleted accounts (also one still marked active) are left out; an assignment recorded under another workspace never counts. An account of another workspace linked under this workspace is left out (the account's own `workspace_id` is compared).
- **R2.** An unknown tag, `tag_id=0`, a tag with no live account, or another workspace → `[]`. **The tag's own `workspace_id` is not compared**: an assignment recorded in this workspace that points to another workspace's tag still counts (that link is invalid data under HR-16, and no API writer creates it; it is a fact of this method, not something to change in this unit). Apart from its `is_active` (R3), nothing of the tag row is looked at.
- **R3.** [BUG-1481] (HR-4) When the tag is deleted (`account_tags.is_active = False`), `[]` is returned; the assignments stay as they are and the accounts are listed again once the tag is active. *(Today: the tag is not looked at — the accounts of a deleted tag are returned.)*
- **R4.** [BUG-1480] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`. *(Today: no `ORDER BY`; plan-dependent.)* The codebase's way of writing this sort (see `app/dao/account_tag.py`, `app/dao/item_tag.py`) is the lower-cased name ascending, then `id` ascending.
- **R5.** `skip` / `limit` after the filters; defaults 0 and 100 (101 matching accounts → 100 returned; `limit=1000` → all 101, each once); `limit=0` → `[]`; a hidden account (inactive, deleted, deleted tag) never takes a place on the page. Negative values raise `DataError` (as below). Each account appears once.
- **Errors:**

  | Condition | Raises | Detail message |
  |---|---|---|
  | negative `limit` | `sqlalchemy.exc.DataError`, pgcode `2201W` | `LIMIT must not be negative` |
  | negative `skip` | `DataError`, pgcode `2201X` | `OFFSET must not be negative` |

- **Side effects:** none. The read writes nothing and leaves the caller's pending (unflushed) changes pending; it does not commit or roll back.

### Other methods of the file (not in a bug of this unit; must not change)
- `get_accounts_in_workspace` — has its own open bugs (§6). Leave it exactly as it is, even though the same `DISTINCT` / ordering note applies there.
- `count_active_accounts` — counts accounts of the workspace with `is_active = True` and `is_deleted = False`; no cap; unknown workspace → `0`.
- `search_by_name_in_workspace` — dead code, listed for removal elsewhere; leave it.
- Inherited generic methods (`create`, `update`, `get`, `get_by_id_and_workspace`, `get_by_workspace`, `get_multi`, `remove`) stay as they are; the raw lookups return deleted and inactive accounts (HR-4 scope).

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Standing decision: no order recipe counts as deterministic unless it ends in `id`.
- **HR-4. Soft-deleted rows are hidden unless asked for.** Filters, joins and searches through related rows ignore related rows that are soft-deleted (a deleted tag neither filters nor matches). Scope: managers and module-specific DAO query methods; the generic base methods stay raw. For account tags, "deleted" is `is_active = False`. Things of a soft-deleted parent are hidden by the parent's state; their own rows are untouched (the assignments are not changed).
- **HR-5. Filter first, then page.** Every filter (account state, assignment workspace, tag state) is in the query, before `LIMIT` / `OFFSET`; a page is only short when there are no more results.
- **HR-16. Nothing links across workspaces.** Keep filtering on the account's `workspace_id` and on the assignment's `workspace_id`. Do not add a comparison of the tag's own `workspace_id` in this unit (R2).
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/account.py`, method `get_accounts_by_tag_id` only.
- No migration, no schema change, no API change. The signature, the keyword-only parameters, the defaults and the return type stay the same.
- Expected shape of the fix (from the bug row): replace the assignment join + `DISTINCT` by an `EXISTS` sub-query on `account_tag_assignments` (assignment's `account_id`, `workspace_id`, `tag_id`) that also requires the tag to be active, and add the HR-6 order before `offset` / `limit`.

## 6. Out of scope (leave alone)

- `app/dao/account.py` `get_accounts_in_workspace` (bugs logged against the account manager "via `app/dao/account.py`"): BUG-861 (tag-code filter exact and case-sensitive), BUG-864 (filtering by a deleted tag still returns accounts), BUG-866 (account search has no sort order), BUG-868 (`%` and `_` act as wildcards), plus the name-trimming and `include_inactive` decisions of its spec (BUG-637 precedent, BUG-878).
- `app/services/account_service.py`: BUG-2982 ("accounts with tag N" answers 200 for a deleted tag — the 404 part of BUG-1481's row), BUG-2983 (`limit` lower bound on `GET /accounts/by-tag/{tag_id}/`), BUG-2984, BUG-2986.
- `app/managers/account_manager.py`: BUG-863, BUG-865, BUG-867, BUG-870, BUG-871, BUG-878, BUG-1487, BUG-2987.
- `app/dao/account_tag_assignment.py`: BUG-1486 (an account's tags have no order).
- BUG-100 (generic `get_by_workspace` / `get_multi` have no order): `app/dao/base.py`.
- The per-account tag reads the service makes for each returned account (one query per account) are known and not part of this unit.
