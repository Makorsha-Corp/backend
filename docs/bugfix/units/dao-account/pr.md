## Fix: "accounts with this tag" comes back in a fixed order, and a deleted tag no longer lists accounts

**Fixes BUG-1481 and BUG-1480.** One file (`app/dao/account.py`). No database change, no API shape change (only the values in the list change).

**Not marked "Good to auto-merge":** the unit is risk `normal`. The ordering bug is on the trivial list, but the deleted-tag bug (`join-ignores-soft-deleted`) is not.

---

### What was wrong

**1. A deleted tag still listed its accounts (BUG-1481). This is the one that matters most.**

When an account tag is deleted, its links to accounts are kept (so it can be restored). But the "accounts with tag N" list never looked at the tag itself, so a deleted tag kept listing every account that still carried it.

*Example:* the tag "Old supplier" is deleted, while "Acme Ltd" and "Karim Traders" still carry it. Asking for the accounts with "Old supplier" returned both accounts, as if the tag were still in use.

**2. The list had no sort order (BUG-1480)**

The list was paged (100 at a time) but not sorted, so the database returned rows in whatever order its plan gave. The order could change after someone edited an account, and when paging, an account could show up on two pages or on none.

*Example:* the tag "Supplier" is on "Zulu", "apple" and "Banana". They came back as `Zulu, apple, Banana`. Now they always come back as `apple, Banana, Zulu`, and two accounts with the same name come back oldest first.

---

### What changed

All in `app/dao/account.py`, method `get_accounts_by_tag_id`:

```diff
- .join(AccountTagAssignment, Account.id == AccountTagAssignment.account_id)
- AccountTagAssignment.workspace_id == workspace_id,
- AccountTagAssignment.tag_id == tag_id
+ exists().where(                                        # "this account carries the tag in this workspace"
+     AccountTagAssignment.account_id == Account.id,
+     AccountTagAssignment.workspace_id == workspace_id,
+     AccountTagAssignment.tag_id == tag_id,
+     AccountTag.id == AccountTagAssignment.tag_id,
+     AccountTag.is_active == True,                      # ...and the tag is not deleted
+ ),
+ .order_by(func.lower(Account.name).asc(), Account.id.asc())   # name ignoring case, then id
- .distinct()
```

- The deleted-tag rule follows **house rule HR-4** (a deleted tag neither filters nor matches). The tag's links are not touched: restoring the tag lists the accounts again.
- The sort follows **house rule HR-6** (every list has a fixed order that ends with id). It is the same order the account tag and item tag lists use.
- The join plus `DISTINCT` became an `EXISTS` check. Postgres refuses to sort by the lower-cased name together with `DISTINCT`, and `EXISTS` already gives each account once.
- Both filters sit in the query before paging (house rule HR-5), so a deleted tag's accounts never take places on a page.

### What you'll notice

- `GET /accounts/by-tag/{tag_id}/` for a **deleted tag now answers 200 with an empty list `[]`** (before: 200 with the tag's accounts). The proper answer, 404 "Account tag {tag_id} not found", comes with **BUG-2982**, a separate fix in the account service.
- The list comes back in the same order every time: by name ignoring upper and lower case, then oldest first for equal names. Paging no longer repeats or skips accounts.
- Deliberately unchanged: the response fields, status codes, inputs and paging limits; inactive and deleted accounts are still left out; the second account list in the same file (account search, BUG-861/864/866/868) is not touched.
- No screen in the frontend uses this endpoint today, so nothing changes for users yet.

### What to look at when reviewing

- **A deleted tag gives `[]` with 200 for now, not 404.** The 404 belongs to the service and is BUG-2982, kept out so this PR stays one file. Object if you'd rather ship both together.
- **The tag's own workspace is not compared.** The query keeps checking the account's workspace and the link's workspace, as before. A link to another workspace's tag can't be created through the app; it was left as it is by the spec, not tightened here.
- **Same problem next door.** Account search in the same file (`get_accounts_in_workspace`) has the same missing order and the same deleted-tag issue (BUG-864, BUG-866, plus BUG-861, BUG-868). It's planned as a later unit for this file.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the only caller is `AccountService.get_accounts_by_tag_id` (`GET /accounts/by-tag/{tag_id}/`). It keeps the order it gets and doesn't re-sort. The query plans as a semi-join on the existing indexes; no new index is needed.
- **Contract:** same shape, codes and inputs; values only (fixed order; a deleted tag lists nothing). No frontend caller of `/accounts/by-tag/`, so no frontend PR.
- **Tests:** the 3 tests marked as known failures for these bugs (2 strict, 1 order test that sometimes passed by luck) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `092776b`). The service test for the 404 (BUG-2982) is still a known failure, as expected.
- **Database:** no migration; Alembic unchanged.
- **Commits:** `43c3f76` on branch `bugfix/dao-account`.

</details>

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 0 minors, 1 nit (strict independent review, `review-1.md`).

Nit (no action): the new comment explaining the `EXISTS` doesn't name the bug ids, unlike an older comment in `factory_section.py`. Leaving the ids out is deliberate: bug ids go in commits and PRs, not code comments.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
