# Fix brief: dao-account_tag

## 1. Unit

| | |
|---|---|
| Slug | `dao-account_tag` |
| Source file | `app/dao/account_tag.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-account_tag` (to be created by the orchestrator) |
| Branch | `bugfix/dao-account_tag` (from `origin/main`; to be created by the orchestrator) |
| Risk | `normal` (BUG-1482 `unordered-pagination` is on the trivial list; BUG-1483 `list-returns-soft-deleted`, BUG-1484 `non-atomic-counter-update` and BUG-1485 `silent-result-cap` are not) |

## 2. Bugs

### BUG-1482: Account tag lists have no sort order; "system tags first" does not happen
- **Pattern:** `unordered-pagination`
- **Where:** `AccountTagDAO.get_active_tags_in_workspace`, `AccountTagDAO.get_system_tags_in_workspace`; reached through `GET /account-tags/`, `GET /account-tags/system/`.
- **Today:** No `ORDER BY` in either list, although `GET /account-tags/` documents "sorted with system tags first"; verified a system tag last and the order changing after an update.
- **Intended:** HR-6: active list — system tags first, then name case-insensitive ascending, then `id` (BUG-930 precedent); system list — name case-insensitive ascending, then `id` (BUG-929 precedent).

### BUG-1483: System tag list includes deleted system tags
- **Pattern:** `list-returns-soft-deleted`
- **Where:** `AccountTagDAO.get_system_tags_in_workspace`; reached through `GET /account-tags/system/`.
- **Today:** No `is_active` filter; a system tag with `is_active = False` is returned (only reachable through data written outside the API: system tags cannot be edited or deleted through it).
- **Intended:** HR-4: deleted system tags are not returned (as the item-tag twin does).

### BUG-1484: Account tag usage counter can lose concurrent changes
- **Pattern:** `non-atomic-counter-update`
- **Where:** `AccountTagDAO.increment_usage_count`, `AccountTagDAO.decrement_usage_count`; reached through account create / update / delete and tag assign / unassign (`AccountManager`, and `AccountTagAssignmentDAO.remove_all_tags_from_account`).
- **Today:** The new value is computed in Python from the loaded object and written back (`SET usage_count = <n>`); the "not below 0" check also uses the loaded value. Loaded 3 / stored 10 → increment stores 4; loaded 3 / stored 0 → decrement stores 2.
- **Intended:** The change is applied **in the database, relative to the stored value, in one UPDATE statement**: `usage_count = usage_count + 1` for the increase; `usage_count = usage_count - 1` with the condition `usage_count > 0` in the same statement's WHERE for the decrease. The returned tag shows the stored result. No row lock (per BUG-931; decided by Claude under the reviewer's delegation (2026-11-03)). Re-reading the counter and then writing an absolute number is **not** a fix: two requests can still both read 5 and both write 6.
- **Example:** Two users each tag an account "Supplier" (counter 5) at the same second. Both requests read 5 and write 6: seven accounts carry the tag, the counter says 6 for ever. After the fix it says 7.

### BUG-1485: Account tag picker silently stops at 100 tags
- **Pattern:** `silent-result-cap`
- **Where:** `AccountTagDAO.get_active_tags_in_workspace`; reached through `GET /account-tags/`.
- **Today:** Default `limit=100`, never passed by the caller; tag 101 onwards missing, and with no order (BUG-1482) which ones vary.
- **Intended:** Every active tag returned, no cap; the unused `skip` / `limit` go with the fix (per BUG-982; decided by Claude under the reviewer's delegation (2026-11-03)).
- **Signature change:** the method becomes `get_active_tags_in_workspace(db, *, workspace_id)`. Its only caller, `AccountTagService.get_tags` (`app/services/account_tag_service.py`), passes only `workspace_id`; no other code in `app/` calls it.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `account_tags`; `is_active = False` **is the soft delete** for account tags (there is no `is_deleted`). `usage_count` is integer NOT NULL, Python default `0`, no check constraint (a negative value can be stored by a direct write). `is_system_tag` and `is_active` are NOT NULL with Python defaults. No `updated_at` / `updated_by` columns. No unique index on `tag_code` or `name`. Every parameter after `db` is keyword-only in all five methods (a positional call raises `TypeError`). The class never commits; the counters flush.

### `AccountTagDAO.get_by_tag_code_in_workspace(db, *, workspace_id, tag_code)` (not in a bug; must not change)
Used by `AccountTagService.create_tag` ← `POST /account-tags/`, as the duplicate check (anything found → 409). Returns the `AccountTag`, or `None`.
- **R1.** Given a tag of the workspace with exactly that code, it is returned; a tag of another workspace with that code never is; an unknown workspace → `None`.
- **R2.** Exact comparison: for stored `supplier`, the codes `Supplier`, `" supplier"`, `sup` and `sup%` return `None`; `None` returns `None`.
- **R3.** A deleted tag (`is_active = False`) is returned like an active one; `is_system_tag` does not matter (raw lookup, decided).
- **R4.** Given two tags of the workspace with one code, one of them is returned; which one is not specified.
- Errors: none. Side effects: none.

### `AccountTagDAO.get_active_tags_in_workspace(db, *, workspace_id)`
Used by `AccountTagService.get_tags` ← `GET /account-tags/` (the tag picker of the account forms; no paging; the service returns the list unchanged, with the stored `usage_count`). Returns a `list` of `AccountTag` (possibly empty).
- **R1.** Returns the tags of `workspace_id` with `is_active = True`, system and user tags alike. Deleted tags and other workspaces' tags never; an unknown or empty workspace → `[]`.
- **R2.** [BUG-1485] Every matching tag is returned: given 101 active tags, 101. *(Today: at most 100 — `limit=100` by default and never passed.)* A deleted tag never takes a place in the result.
- **R3.** [BUG-1482] (HR-6) Every system tag comes before every user tag. *(Today: no ordering; verified a system tag last.)*
- **R4.** [BUG-1482] (HR-6) Within each group, name case-insensitive ascending, then `id` ascending: user tags "bravo", "Alpha" (lower id), "alpha", "Charlie" come back "Alpha", "alpha", "bravo", "Charlie". *(Today: no `ORDER BY`; the order changed after an update.)*
- Errors: none. Side effects: none (writes nothing, leaves the caller's pending changes pending).

### `AccountTagDAO.get_system_tags_in_workspace(db, *, workspace_id)`
Used by `AccountTagService.get_system_tags` ← `GET /account-tags/system/` (returned unchanged). Returns a `list` of `AccountTag` (possibly empty).
- **R1.** Returns tags of `workspace_id` with `is_system_tag = True`; user tags and other workspaces' tags never; unknown workspace or none → `[]`. No limit (101 system tags → 101).
- **R2.** [BUG-1483] (HR-4) A deleted system tag (`is_active = False`) is not returned. *(Today: returned.)*
- **R3.** [BUG-1482] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending ("Utility", "client", "Bank" → "Bank", "client", "Utility"). *(Today: no `ORDER BY`.)*
- Errors: none. Side effects: none (writes nothing, leaves the caller's pending changes pending).

### `AccountTagDAO.increment_usage_count(db, *, tag_id, workspace_id)`
Used by `AccountManager._assign_tags_to_account` and `AccountManager.assign_tag`. Returns the `AccountTag` (the session's instance), or `None`.
- **R1.** A tag with that id in that workspace: stored `usage_count` + 1 (2 → 3); the same instance the session holds is returned. Other tags are untouched.
- **R2.** Unknown id or another workspace's tag → `None`, nothing written, no error (decided: callers check the tag first).
- **R3.** A deleted tag and a system tag are counted like any other (raw write, decided).
- **R4.** No bound and no sign check: a stored −2 becomes −1.
- **R5.** [BUG-1484] The increase applies to the value stored at that moment: loaded object 3 / stored 10 → stored 11, and the returned tag shows 11. *(Today: 4 is stored and returned. With a freshly loaded or expired object: 11 already.)* See BUG-1484 Intended: one relative UPDATE in the database.
- **R6.** Flushed, not committed: a savepoint roll-back around the call restores the old value; no commit is made. The flush also writes any other pending change of the session (an unflushed rename of the same tag is saved with it).
- Errors: none. Side effects: at most one row's `usage_count` changed, flushed.

### `AccountTagDAO.decrement_usage_count(db, *, tag_id, workspace_id)`
Used by `AccountManager.unassign_tag` and `AccountTagAssignmentDAO.remove_all_tags_from_account` (once per assignment). Returns the `AccountTag`, or `None`.
- **R1.** A tag of the workspace with `usage_count` above 0: stored − 1 (3 → 2, 1 → 0); the tag is returned. Other tags are untouched.
- **R2.** `usage_count = 0`: nothing written, the tag is returned with 0, and **nothing is flushed** (another pending change of the session, such as an unflushed rename, stays unsaved).
- **R3.** A negative stored value: nothing written, the tag is returned unchanged (−2).
- **R4.** Unknown id or another workspace's tag → `None`, nothing written, no error (decided).
- **R5.** A deleted tag and a system tag are decremented like any other (raw write, decided).
- **R6.** [BUG-1484] The decrease and the "not below 0" check use the value stored at that moment: loaded 3 / stored 10 → 9; loaded 3 / stored 0 → stays 0; the returned tag shows the stored result in both cases. *(Today: 2 in both cases.)* See BUG-1484 Intended: one relative UPDATE with the `usage_count > 0` condition in its WHERE.
- **R7.** When a value is written: flushed, not committed (as `increment_usage_count` R6, including the flush of other pending changes).
- Errors: none. Side effects: at most one row's `usage_count` changed, flushed when changed.

### Inherited generic methods (not overridden; must not change)
`create`, `update`, `get`, `get_by_id_and_workspace`, `get_by_workspace`, `get_multi`, `remove` stay as they are. The raw lookups return deleted tags like active ones (HR-4 scope). `create` checks no uniqueness. `get_by_workspace` / `get_multi` ordering is BUG-100, in `app/dao/base.py`, not here.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Standing decision: no order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen first key (here: system tags first), keep it and add the name and `id` keys after it.
- **HR-4. Soft-deleted rows are hidden unless asked for.** Lists and searches exclude soft-deleted rows by default. Scope: managers and module-specific DAO query methods; the generic base methods (`get`, `get_by_id_and_workspace`, `get_by_workspace`, `get_multi`) stay raw. For account tags, "deleted" is `is_active = False`.
- **HR-10. Harmful state transitions lock the row** only for money, stock quantities, approvals or duplicate side effects. A tag usage counter is none of these: **no row lock** (`SELECT … FOR UPDATE` is not wanted). The fix is a single relative UPDATE in the database.
- **HR-16. Nothing links across workspaces.** Every method keeps filtering on the tag's `workspace_id`.
- Hidden caps are bugs (BUG-342, BUG-982 precedent): a list with no paging from the API returns every row.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/account_tag.py` only.
- No migration, no schema change, no API change. The two counters keep their signatures and return the tag or `None`. `get_active_tags_in_workspace` loses its `skip` and `limit` parameters (BUG-1485); nothing passes them.

## 6. Out of scope (leave alone)

- `app/dao/account_tag_assignment.py`: BUG-1486 (an account's tags have no order).
- `app/managers/account_manager.py`: BUG-1487 (saving tags erases links to deleted tags), BUG-861, BUG-865, BUG-870, BUG-871, BUG-2987 (deleted tags accepted on account create / update).
- `app/dao/account.py`: BUG-1480, BUG-1481 (accounts of one tag: order, deleted tag).
- `app/services/account_service.py`: BUG-2982 ("accounts with tag N" answers 200 for a deleted tag).
- `app/services/account_tag_service.py`: BUG-1683, BUG-1685, BUG-1688, BUG-1689, BUG-1690, BUG-1691; `app/schemas/account_tag.py`: BUG-1682, BUG-1692, BUG-1693; `account_tags` table: BUG-1684.
- BUG-100 (generic `get_by_workspace` has no order): `app/dao/base.py`.
- The annotation of the two counters (`-> AccountTag` although they can return `None`) is known and not a bug; it may be corrected to `AccountTag | None` if the fix touches those lines anyway.
