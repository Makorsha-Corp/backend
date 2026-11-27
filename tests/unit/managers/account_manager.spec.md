# Spec — `app/managers/account_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092

> **Review note:** the reviewer accepted every suggested answer on 2026-10-10, after the answers had first been applied as pilot defaults.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-1** `create_account` R2, `update_account` R6 — account names are stored exactly as typed (`"  Acme  "` keeps its spaces) and a whitespace-only name (`"   "`) is accepted. Intended: name stored trimmed; blank / whitespace-only rejected by `AccountCreate` / `AccountUpdate` (422), nothing written (fix in `app/schemas/account.py`).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-860. Rules: `create_account` R2, `update_account` R6.
- **HR-3** `search_accounts` R8 — the `tag_code` filter is an exact, case-sensitive match (`Supplier` or `supplier ` finds nothing when the code is `supplier`). Intended: filter value trimmed and compared case-insensitively.
**Answer:** bug — per HR-3 (house rule)
**Resolution:** 🐞 BUG-861. Rules: `search_accounts` R8.
- **HR-4** `get_account` R4 — a soft-deleted account is returned by id. Intended: soft-deleted → `None` by default (404 at the API); new `include_deleted=True` parameter returns it.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-862. Rules: `get_account` R4.
- **HR-4** `update_account` R3 — a soft-deleted account can still be edited (including `is_active: true`, leaving a row that is both deleted and active). Intended: soft-deleted is treated as not found (`Account {id} not found`), nothing written.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-863. Rules: `update_account` R3.
- **HR-4** `assign_tag` R3, `unassign_tag` R3 — tags can be assigned to / removed from a soft-deleted account. Intended: soft-deleted account treated as not found (`Account {id} not found`), nothing written.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-863 (same root cause as the `update_account` line above). Rules: `assign_tag` R3, `unassign_tag` R3.
- **HR-4** `search_accounts` R9 — filtering by `tag_code` also matches tags that were deleted (tags are soft-deleted with `is_active = False`, their assignments stay). Intended: only active tags match the filter.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-864. Rules: `search_accounts` R9.
- **HR-4** `get_tags_for_account` R4 — deleted (inactive) tags are still returned as tags of the account. Intended: only active tags are returned.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-865. Rules: `get_tags_for_account` R4.
- **HR-6** `search_accounts` R11 — no sort order; paging can repeat or skip accounts. Intended: name case-insensitive ascending, then `id` ascending, before `skip`/`limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-866. Rules: `search_accounts` R11.
- **HR-7** `search_accounts` R13 — `GET /accounts/` has no lower bound on `limit` (`0` → empty list, negative → database error / 500). Intended: `limit >= 1`, 422 otherwise (fix in the endpoint).
**Answer:** bug — per HR-7 (house rule)
**Resolution:** 🐞 BUG-867. Rules: `search_accounts` R13.
- **HR-8** `search_accounts` R4 — the name search text is put into `ILIKE '%…%'` unescaped; `%` or `_` alone matches every account. Intended: `%`, `_` and `\` match literally.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** 🐞 BUG-868. Rules: `search_accounts` R4.
- **HR-9** `update_account` R8 — `updated_by` is written on every successful update, even an empty request or unchanged values. Intended: written only when at least one field or the tag set actually changes.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-869. Rules: `update_account` R8.
- **HR-9** `update_account` R13 — when `tag_ids` is sent, every existing tag assignment is deleted and re-created, so tags that did not change get a new "assigned at" time and "assigned by" = the user who saved the form. Intended: tags that stay keep their assignment row (`assigned_at`, `assigned_by`) untouched; only removed tags are deleted and new tags added.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-870. Rules: `update_account` R13.

### Precedent matches — confirm all with ok

### P1. Editing or deleting a missing account answers 500 — 🐞 BUG-2986
**Background:** `update_account` and `delete_account` report problems with a plain Python `ValueError`. `AccountService.update_account` / `delete_account` do not translate it (the tag endpoints do), and the app has no `ValueError` handler, so it becomes the generic 500.
**What happens today:** `PUT /accounts/{id}/` for an id that does not exist (or belongs to another workspace) answers 500. `DELETE /accounts/{id}/` on an already-deleted account answers 500 ("already deleted").
**Example:** A user has an account open in two tabs, deletes it in one and presses Delete again in the other: "internal server error" instead of "not found".
**Rules affected:** `update_account` R1, R2; `delete_account` R1, R2, R3
**Answer:** bug — per BUG-124 precedent (same pattern; logged for accounts as BUG-2986): these rejections reach the client as 4xx, never 500 — not found → 404 `Account with ID {id} not found`, already deleted → 400; the manager keeps raising `ValueError`, the caller (`AccountService`) translates it as it already does for `assign_tag` (precedent — confirm)
**Resolution:** BUG-2986 (opened 2026-11-22; first cited as BUG-2986 by pattern, whose row is the attachment allowlist bug). Rules: `update_account` R1a, `delete_account` R1a (service-level, integration-only).

### P2. "Belongs to another workspace" message reveals that the account id exists — 🐞 BUG-440 (existing)
**Background:** `get_account`, `assign_tag` and `unassign_tag` deliberately answer "not found" for an account of another workspace ("don't leak existence"). `update_account` and `delete_account` use a different message for that case.
**What happens today:** For an id that exists in another workspace they raise `Account {id} does not belong to workspace {workspace_id}`; for a non-existent id `Account {id} not found`.
**Example:** Workspace A calls update on account 812 (workspace B): the error text confirms account 812 exists somewhere (today hidden behind the 500 of P1; visible once P1 is fixed).
**Rules affected:** `update_account` R2, `delete_account` R2
**Answer:** bug — per BUG-440 precedent: an account of another workspace gets exactly the same error as a non-existent one, `Account {id} not found` (precedent — confirm)
**Resolution:** referenced existing BUG-440 (no new ID). Rules: `update_account` R2, `delete_account` R2.

### P3. Account audit rows never record IP address or user agent — 🐞 BUG-140 (existing)
**Background:** Every create / update / delete of an account writes a financial audit row. The audit table has `ip_address` and `user_agent` columns, but the manager has no way to receive them.
**What happens today:** Both columns are always `NULL` on account audit rows.
**Example:** An investigator checking who changed a supplier's bank details sees the user id and time, but no IP or device.
**Rules affected:** `create_account` R10, `update_account` R18, `delete_account` R10
**Answer:** bug — per BUG-140 precedent: the request's client IP and user agent are passed endpoint → service → manager into every `log_financial_audit` call of `create_account` / `update_account` / `delete_account` (requires new `ip_address` / `user_agent` parameters) (precedent — confirm)
**Resolution:** referenced existing BUG-140 (no new ID). Rules: `create_account` R10, `update_account` R18, `delete_account` R10.

### P4. Optional account details cannot be cleared — 🐞 BUG-608 / BUG-753 (existing)
**Background:** The update drops every field sent as `null` (`exclude_none`), so "set to empty" looks the same as "not sent".
**What happens today:** Once set, `account_code`, contact persons, emails, phones, address, city, country, postal code, payment preferences and bank details can only be replaced, never removed. The response is 200 as if it worked.
**Example:** A supplier's old bank details must be removed. The user clears the field; the client sends `"bank_details": null`; the old details stay.
**Rules affected:** `update_account` R5
**Answer:** bug — per BUG-608 / BUG-753 precedent: an explicit `null` clears the nullable fields (`account_code`, all contact, address, `payment_preferences`, `bank_details`); `null` for `name`, `allow_invoices` or `is_active` is rejected with 422; omitted fields stay unchanged; `tag_ids: null` keeps meaning "leave tags unchanged" (precedent — confirm)
**Resolution:** referenced existing BUG-608 (pattern of BUG-753) (no new ID). Rules: `update_account` R5.

### P5. "Account updated" audit row written when nothing changed — 🐞 BUG-632 (existing)
**Background:** The financial audit log is the record of changes to accounts.
**What happens today:** Every successful `update_account` call writes an `updated` audit row with identical before/after values, even for an empty request.
**Example:** A user opens the edit form and presses Save without changing anything: the audit log shows "Account 'Acme' updated" with before = after.
**Rules affected:** `update_account` R15
**Answer:** bug — per BUG-632 precedent: the `updated` audit row is written only when at least one field or the tag set actually changed value (precedent — confirm)
**Resolution:** referenced existing BUG-632 (no new ID). Rules: `update_account` R15.

### P6. Whitespace-only (or padded) name search returns almost nothing — 🐞 BUG-637 (existing)
**Background:** The search text is used as typed, without trimming.
**What happens today:** A search of `"   "` only matches accounts whose name contains three spaces in a row; `" acme "` does not find "Acme Ltd".
**Example:** `GET /accounts/?search=%20%20%20` returns `[]` although 40 accounts exist.
**Rules affected:** `search_accounts` R5
**Answer:** bug — per BUG-637 precedent: the search text is trimmed; blank / whitespace-only after trimming means no name filter (precedent — confirm)
**Resolution:** referenced existing BUG-637 (no new ID). Rules: `search_accounts` R2, R5.

### P7. An account's tags come back in no fixed order — 🐞 BUG-1486
**Background:** The tag list of an account is read without `ORDER BY`.
**What happens today:** The order of `account_tags` in every account response can differ between calls.
**Example:** An account tagged "Supplier" and "Client" shows the chips as Supplier · Client on one load and Client · Supplier on the next.
**Rules affected:** `get_tags_for_account` R5
**Answer:** bug — per BUG-008 / BUG-932 precedent (HR-6): tags ordered by name case-insensitive ascending, then `id` ascending; system tags are not grouped first (precedent — confirm)
**Resolution:** 🐞 BUG-1486 (pattern `unordered-pagination`, logged by the `account_tag_assignment` DAO describer, which owns the fix). Rules: `get_tags_for_account` R5. *Corrected 2026-11-03 (DAO describer, FU-1 (a)):* this question first cited BUG-719, which is an inventory bug (per-type breakdown of inventory stats); BUG-1486 is the register row for this order, and its "system tags not grouped first" clause was added to R5.

### P8. Create / update accept a deleted (inactive) tag that "assign tag" refuses — 🐞 BUG-2987
**Background:** Tags are soft-deleted (`is_active = False`). The single-tag endpoint (`assign_tag`) refuses an inactive tag with "Account tag N is not active". Creating or updating an account with `tag_ids` goes through a different helper that only checks the tag exists in the workspace.
**What happens today:** An inactive tag id in `tag_ids` is assigned normally and its usage count goes up.
**Example:** Tag 7 "Old vendor" was deleted. `POST /accounts/` with `tag_ids: [7]` creates the account with tag 7 attached; `POST /accounts/{id}/tags/7/` on the same account would answer "not active".
**Rules affected:** `_assign_tags_to_account` R6, `create_account` R6, `update_account` R11
**Answer:** bug — per BUG-629 precedent (same pattern; logged for accounts as BUG-2987): tags added through create / update pass the same checks as `assign_tag`: an inactive tag is rejected with `Account tag {id} is not active`, nothing written (on update the check applies to tags being newly added) (precedent — confirm)
**Resolution:** BUG-2987 (opened 2026-11-22; first cited as BUG-2987 by pattern, whose row is the invoice account-change bug). Rules: `_assign_tags_to_account` R6, `create_account` R6b, `update_account` R11a.

### P9. Saving an account's tags erases its links to deleted tags — 🐞 BUG-1487
**Background:** A tag is deleted by `is_active = False`; its links to accounts stay and are hidden from the account's tag list (`get_tags_for_account` R4), so they can come back if the tag is restored. When `tag_ids` is sent, `update_account` first deletes **every** link of the account, including links to deleted tags, and lowers those tags' counters. The form cannot re-send a tag it does not show.
**What happens today:** After any tag save, the account has no link to a deleted tag, and each such tag's `usage_count` has dropped by 1.
**Example:** Tag "Importer" is on 30 accounts and is deleted by mistake. During the week 5 of those accounts are edited and saved. Support restores "Importer": it is on 25 accounts.
**Rules affected:** `update_account` R11, R12, R13a
**Answer:** bug — per BUG-935 precedent ("hidden, not cascaded"): a tag save touches only the account's links to active tags; links to deleted tags are left as they are (no counter change), hidden while the tag is deleted and shown again once it is restored (precedent — confirm)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03), raised by the `account_tag_assignment` DAO describer (its spec P3, FU-1 (b)): 🐞 BUG-1487 (pattern `replace-all-erases-hidden-rows`, already logged). Rules: new `update_account` R13a; R11 and R12 point to it.

### New questions

### Q1. Unknown tag ids are silently dropped on create / update — 🐞 BUG-871
**Background:** `tag_ids` may contain ids that do not exist or belong to another workspace. The helper skips them without an error. On update, all existing tags are removed *before* the new list is processed.
**What happens today:** The call succeeds; invalid ids are ignored. On update the account can end up with fewer tags than before, or none.
**Example:** An account has tags [3 Supplier]. The client sends `tag_ids: [3, 999]` where 999 was a typo → 200, tags = [3] and nobody learns 999 was ignored. With `tag_ids: [999]` → 200 and the account now has no tags at all.
**Rules affected:** `_assign_tags_to_account` R2, `create_account` R6, `update_account` R14
**Answer:** bug — a tag id that does not exist in the workspace rejects the whole create / update with `Account tag {id} not found` (404 at the API), nothing written (reviewer accepted suggestion)
**Resolution:** unknown tag ids reject the whole call; all tag ids are validated before anything is written (best-practice default, delegated by reviewer). Rules: `_assign_tags_to_account` R2, R7, `create_account` R6a, `update_account` R14.

### Q2. Audit trail does not record bank details and several other fields — 🐞 BUG-872
**Background:** Each audit row stores a before/after snapshot of a fixed list of fields. Create: name, primary contact, primary email, address, city, country. Update: the same plus payment preferences and allow-invoices. Delete: name, primary contact, primary email only.
**What happens today:** Changes to `bank_details`, `account_code`, both phones, the secondary contact / email, `postal_code`, `is_active` and the account's tags never appear in any audit row. (On create, `payment_preferences` and `allow_invoices` are missing too.)
**Example:** Someone replaces a supplier's bank details with their own. The audit log shows "Account 'Acme' updated" with identical before and after — the one change that matters for payment fraud is invisible.
**Rules affected:** `create_account` R9, `update_account` R16, `delete_account` R5
**Answer:** bug — the audit snapshot covers every editable business field (name, account_code, both contacts / emails / phones, address, city, country, postal_code, payment_preferences, bank_details, allow_invoices, is_active) plus the list of tag ids, on create (`after`), update (`before` / `after`) and delete (`before`) (reviewer accepted suggestion)
**Resolution:** full snapshot on all three audit rows. Rules: `create_account` R9, `update_account` R16, `delete_account` R5.

### Q3. Assigning or removing a single tag leaves no trace — 🐞 BUG-873
**Background:** Tags decide what an account is (supplier, client, …). Create / update / delete write an audit row and stamp the account; the single-tag endpoints do neither.
**What happens today:** `assign_tag` and `unassign_tag` write no financial audit row and leave the account's `updated_by` / `updated_at` untouched. A removed tag leaves nothing behind (the assignment row is deleted).
**Example:** A user removes the "Client" tag from an account; later nobody can tell who did it or when.
**Rules affected:** `assign_tag` R8, `unassign_tag` R7
**Answer:** bug — a real assign / unassign writes an `account` `updated` audit row (before / after tag ids) and sets the account's `updated_by`; the idempotent "already assigned" no-op writes nothing (requires new `user_id` parameter on `unassign_tag`) (reviewer accepted suggestion)
**Resolution:** audit row + `updated_by` stamp on real assign/unassign; `unassign_tag` gains `user_id`. Rules: `assign_tag` R8, `unassign_tag` R7.

### Q4. Two accounts can share the same account code — 🐞 BUG-874
**Background:** `account_code` is the optional internal reference of an account. `AccountService.create_account`'s docstring says it raises a conflict "if account with same code exists", but nothing checks it and the database has no unique constraint.
**What happens today:** Any number of live accounts in one workspace can have the same `account_code` (create and update).
**Example:** "Acme Ltd" has code `SUP-001`. A user creates "Beta Traders" with code `SUP-001`: 201, both accounts now carry `SUP-001`.
**Rules affected:** `create_account` R11, `update_account` R20
**Answer:** bug — a non-empty `account_code` is unique per workspace among live accounts, compared trimmed and case-insensitively, backed by a partial unique index; a duplicate answers 409, nothing written (same shape as HR-2) (reviewer accepted suggestion)
**Resolution:** account-code uniqueness as HR-2 (the manager raises `ValueError("Account code '{code}' already exists")`, translated to 409; database partial unique index as backstop); the code is stored trimmed and a blank code is "no code" (`NULL`) — error type / wording and the stored form added in fill-gaps G2 (best-practice default, delegated by reviewer). Rules: `create_account` R11a, R11b, `update_account` R20a, R20b.

### Q5. Two accounts can have the same name — ✅ intended
**Background:** Department names are unique per workspace (HR-2). Account names have no such check.
**What happens today:** Any number of live accounts in a workspace can have exactly the same name.
**Example:** A user creates "Acme Ltd" twice; both exist and both appear in pickers with nothing to tell them apart except the id.
**Rules affected:** `create_account` R11, `update_account` R20
**Answer:** intended (reviewer accepted suggestion; note it deliberately departs from the HR-2 shape used for departments)
**Resolution:** duplicate account names stay allowed. Rules: `create_account` R11 ✅, `update_account` R20 ✅.

### Q6. Email fields accept any text — 🐞 BUG-875
**Background:** `primary_email` and `secondary_email` are plain strings of up to 255 characters; nothing checks they look like an email address.
**What happens today:** Any text is stored as typed.
**Example:** A user saves `primary_email: "call me"`; it is stored and shown as the account's email.
**Rules affected:** `create_account` R12, `update_account` R4
**Answer:** bug — `AccountCreate` / `AccountUpdate` trim both email fields and reject a value that is not a valid email address with 422 (fix in `app/schemas/account.py`) (reviewer accepted suggestion)
**Resolution:** schema-level trim + email validation. Rules: `create_account` R12, `update_account` R4a.

### Q7. An account with open invoices can be deleted — 🐞 BUG-876
**Background:** Deleting an account is a soft delete: the row stays, flagged deleted and inactive, and disappears from account lists and pickers. Its invoices are not touched.
**What happens today:** `delete_account` never looks at the account's invoices or orders; an account with draft, unpaid or partially paid invoices is deleted like any other.
**Example:** "Acme Ltd" has an unpaid payable invoice of 50,000. A user deletes the account: 204. The account vanishes from the accounts list while the 50,000 is still owed.
**Rules affected:** `delete_account` R7
**Answer:** bug — deletion is refused with 400 ("Account has open invoices — settle or void them first") when the account has any non-voided invoice that is a draft or has an outstanding balance (unpaid / partial); nothing changed (reviewer accepted suggestion)
**Resolution:** delete blocked by open invoices. "Open" = draft, or confirmed with payment status unpaid / partial; checked after the not-found / other-workspace / already-deleted checks; no row lock (HR-10 does not apply to a soft delete) — definition, order and lock decision added in fill-gaps G1 / G8 (best-practice default, delegated by reviewer). Rules: `delete_account` R7, R7a–R7d.

### Q8. Deleting an account leaves its tags and the tags' usage counts unchanged — 🐞 BUG-877
**Background:** Each tag has a `usage_count` ("number of accounts with this tag") that goes up on assign and down on unassign.
**What happens today:** Deleting an account keeps all its tag assignments and does not lower any usage count, so deleted accounts are still counted.
**Example:** Tag "Supplier" is on 3 accounts (`usage_count = 3`). Two are deleted. The tag still shows 3 although only one live account has it.
**Rules affected:** `delete_account` R6
**Answer:** bug — deleting an account lowers `usage_count` by one (never below 0) for each tag assigned to it; the assignment rows are kept (reviewer accepted suggestion)
**Resolution:** usage counts follow live accounts. Rules: `delete_account` R6.

### Q9. Deactivated accounts cannot be listed — 🐞 BUG-878
**Background:** An account can be deactivated through update (`is_active: false`) without deleting it. The list / search only ever returns active accounts and has no option to include others.
**What happens today:** A deactivated account can still be opened by id but never appears in `GET /accounts/`, so it cannot be found again to reactivate it.
**Example:** A user switches "Acme Ltd" to inactive. It disappears from the accounts list; the only way back is knowing its id.
**Rules affected:** `search_accounts` R1, `update_account` R7
**Answer:** bug — `search_accounts` gains an `include_inactive` option (default `False` = today's behavior) that also returns inactive, not-deleted accounts, reachable from `GET /accounts/` (reviewer accepted suggestion)
**Resolution:** `include_inactive` option, exposed on the API (per BUG-010 pattern). Rules: `search_accounts` R1, R1a; `update_account` R7.

### Q10. Removing a tag that is not assigned answers 422, the API documents 404 — 🐞 BUG-879
**Background:** The service turns the manager's `ValueError` into 404 only when its text contains "not found"; anything else becomes 422 "business rule violation". The endpoint is documented as "Raises 404 if the tag is not assigned".
**What happens today:** `unassign_tag` raises `Tag {tag_id} is not assigned to account {account_id}` — no "not found" in it — so the API answers 422. The same happens for a tag id that does not exist at all.
**Example:** `DELETE /accounts/5/tags/9/` when tag 9 is not on account 5 → 422 instead of the documented 404.
**Rules affected:** `unassign_tag` R4
**Answer:** bug — answers 404 as documented; the manager's error for this case is `Tag {tag_id} assignment not found for account {account_id}` (so the existing translation yields 404) (reviewer accepted suggestion)
**Resolution:** new message wording so the existing translation yields 404. Rules: `unassign_tag` R4.

### Q11. "Input has no tag_ids attribute" checks can never be false — remove
**Background:** `create_account` and `update_account` both test `hasattr(account_data, 'tag_ids')` before reading it. Their inputs are always `AccountCreate` / `AccountUpdate`, which always have that field.
**What happens today:** The "no attribute" side of both checks is never taken from the API (in a unit test it can only be reached on create by passing a different schema class such as `AccountBase`).
**Example:** No request can reach it; the checks only add an untestable branch.
**Rules affected:** `create_account` R7, `update_account` R10
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** the `hasattr` checks are dead code, logged in `docs/testing/dead-code-removal-checklist.md`; `create_account` R7 deleted; `update_account` R10 keeps only the reachable `tag_ids` not sent / `null` case. Not a bug — no BUG ID.

## Overview
`AccountManager` owns accounts — the external parties the workspace does business with (suppliers, clients, utilities, …) — and their tag assignments. It is called only by `AccountService` (which commits and builds the API responses) behind the `/accounts/` endpoints. It is meant to keep accounts inside their workspace, soft-delete instead of erase, keep each tag's `usage_count` in step with its assignments, and leave a financial audit row for every create / update / delete. Nothing here commits; every write is flushed.

**Callables:** 9 specified · 1 not specified (plus 2 dead branches to be removed)
**Externals to mock:** `utcnow` (`app.managers.account_manager.utcnow` for `deleted_at`; `app.utils.audit_logger.utcnow` for the audit row's `performed_at`). A tag assignment's `assigned_at` is a column default bound at import and is not controllable by patching — assert only that it is set.
**Integration-only behavior:** translation of the manager's `ValueError`s into HTTP statuses (BUG-2986, BUG-879, open-invoices 400, duplicate code 409, unknown tag 404), the `limit` bound on `GET /accounts/` (HR-7), exposing `include_inactive` / `include_deleted` and the client IP / user agent (BUG-140) live in `AccountService` / the endpoint.

**Facts for the test designer**
- Tables: `accounts`, `account_tags`, `account_tag_assignments` (unique on `(account_id, tag_id)`), `financial_audit_logs`.
- Account soft delete = `is_deleted = True` (+ `is_active = False`, `deleted_at`, `deleted_by`). Tag soft delete = `account_tags.is_active = False`; a deleted tag keeps its assignments.
- `created_by`, `updated_by`, `deleted_by`, `assigned_by`, `performed_by` reference `profiles.id`; `workspace_id` references `workspaces.id`.
- An audit row here always has `entity_type = 'account'`, `entity_id` = the account id, `workspace_id` and `performed_by` from the arguments, `related_entity_type` / `related_entity_id` `NULL`.
- Account `name` is not unique (Q5, intended); `account_code` is intended to be unique per workspace among live accounts, trimmed and case-insensitive (Q4, BUG-874) — today there is no uniqueness on either.
- The intended full audit snapshot ("full snapshot") has exactly the keys `name`, `account_code`, `primary_contact_person`, `primary_email`, `primary_phone`, `secondary_contact_person`, `secondary_email`, `secondary_phone`, `address`, `city`, `country`, `postal_code`, `payment_preferences`, `bank_details`, `allow_invoices`, `is_active`, `tag_ids` (list of the account's tag ids, ascending).

- **Constructor (G6):** `AccountManager()` takes no arguments (`from app.managers.account_manager import AccountManager`). The module also exposes a ready-made instance, `account_manager`. The manager holds no per-call state, so one instance can serve every test.
- **`account_tags` columns (G4):** `id`, `workspace_id` (required), `name` (required, ≤ 100), **`tag_code`** (required, ≤ 50 — the column is called `tag_code`, not `code`), `color` (≤ 7), `icon` (≤ 50), `description`, `is_system_tag` (required), `is_active` (required), `usage_count` (required), `created_at` (required), `created_by` (nullable → `profiles.id`). None of the required columns has a database default: inserted through the ORM model `AccountTag` (`app.models.account_tag`) the model fills `is_system_tag = False`, `is_active = True`, `usage_count = 0`, `created_at` = now, so only `workspace_id`, `name` and `tag_code` must be given; a raw SQL insert must give all of them.
- **`account_tags` has no uniqueness at all in the database (G4):** only the primary key — no unique constraint or index on `name` or `tag_code`, and no check constraint. Two tags of one workspace may share a `tag_code`, and may have names differing only in case (`"ALPHA"` / `"alpha"`), when inserted directly. (A duplicate `tag_code` is refused only in Python, by `AccountTagService` when a tag is created through the API; tag names are never checked.)
- **Invoices (G1)** — table `account_invoices`, ORM model `AccountInvoice` (`app.models.account_invoice`). An invoice belongs to an account through `account_id` (→ `accounts.id`, `ON DELETE RESTRICT`) and carries its own `workspace_id` (always the account's workspace). Invoices have no soft-delete column: a draft is removed by a real delete, anything else is voided.
  - Columns that must be set: `workspace_id`, `account_id`, `invoice_type` (`'payable'` or `'receivable'`), `invoice_amount` (numeric 15,2), `invoice_date` (date), `invoice_status`, `paid_amount`, `payment_status`, `allow_payments`. Through the ORM model the last four default to `'draft'`, `0`, `'unpaid'`, `True`, so only the first five are mandatory there; a raw SQL insert must give all nine. `receiving_started` (default `false`) and `created_at` (default now) are filled by the database. Everything else is nullable (`order_type`, `order_id`, `invoice_number`, `vendor_invoice_number`, `due_date`, `payment_locked_reason`, `description`, `notes`, `void_note`, `last_synced_at`, `created_by`, `updated_at`, `updated_by`).
  - No check or unique constraints: the status columns are plain strings, kept consistent only by the invoice code. Tests must insert rows in one of the consistent states below.
  - `invoice_status` — lifecycle: `'draft'` → `'confirmed'` → `'voided'` (terminal). `payment_status` — `'unpaid'` (`paid_amount = 0`), `'partial'` (`0 < paid_amount < invoice_amount`), `'paid'` (`paid_amount >= invoice_amount`). (`'overdue'` is documented but never stored by any code — BUG-635 of the invoice manager spec; do not use it in a setup.)
  - The consistent states, as the invoice code leaves them:

    | State | `invoice_status` | `invoice_amount` | `paid_amount` | `payment_status` | Blocks account deletion (`delete_account` R7a)? |
    |---|---|---|---|---|---|
    | draft | `'draft'` | e.g. `1000.00` | `0.00` | `'unpaid'` | yes |
    | confirmed, unpaid | `'confirmed'` | `1000.00` | `0.00` | `'unpaid'` | yes |
    | confirmed, partially paid | `'confirmed'` | `1000.00` | `400.00` | `'partial'` | yes |
    | confirmed, settled | `'confirmed'` | `1000.00` | `1000.00` | `'paid'` | no |
    | voided | `'voided'` | `1000.00` | `0.00` | `'unpaid'` | no |

    Voiding always resets `paid_amount` to `0.00` and `payment_status` to `'unpaid'` and sets `void_note`; so a voided invoice looks "unpaid" in `payment_status` and is told apart only by `invoice_status`.
- **Today's behaviour of `\` in the name search (G5):** the text is placed unescaped into `ILIKE '%…%'` and PostgreSQL's default `LIKE` escape character is the backslash, so a backslash makes the character after it literal instead of matching itself. Verified on the test database: searching `\` (one backslash) builds the pattern `%\%`, which matches only names **ending in a literal `%`** — it finds neither `Acme\Ltd` nor `Acme Ltd`, and returns `[]` when no name ends in `%`; searching `e\L` matches `AcmeLtd` but not `Acme\Ltd`. No error is raised (the pattern never ends in the backslash).

**Notes for the test designer**
- Where a rule says "nothing written" for a rejection raised after the account row could already be flushed, the manager must validate first; a test may check by asserting no new rows exist in the same session after the raise.
- **Today's row order where a rule says "no order" (G7):** it is undefined and depends on the query plan — do not rely on any particular order, and do not rely on it *not* being the intended one for a tiny data set.
  - `search_accounts` runs `SELECT DISTINCT … LIMIT … OFFSET …` with no `ORDER BY`; on the test database this is a hash aggregate, so rows come back in hash order — neither insertion order nor name order, and it can differ from run to run (ids and `created_at` take part in the hash).
  - `get_tags_for_account` is a plain join with no `ORDER BY`; on the test database rows usually come back in the physical (insertion) order of the `account_tags` rows, i.e. normally ascending tag id — but not reliably: the `account_tag_assignment` DAO describer verified the order changing after a tag update (BUG-1486). So a card that compares today's order cannot be relied on to fail; the one dependable alarm for R5 is a check that the SELECT reading the tags carries an `ORDER BY`.
  - So an expected-to-fail ordering case (`search_accounts` R11, `get_tags_for_account` R5) must be built so that today's result cannot equal the intended order by accident: make the intended order differ from both id-ascending and id-descending order, and for `search_accounts` use at least 6 rows so a chance match of the hash order is negligible (1 in 720). For the "then `id`" tie-break of `get_tags_for_account` R5, insert the equal-name tags so that the intended order is not ascending tag id overall (as it is when a later-sorting name is inserted first).
- **`unassign_tag` and the future `user_id` (G3):** `user_id` will be a required argument (see that callable's Inputs). Today the parameter does not exist, so a call that passes it fails with `TypeError` and a call that omits it works; after the BUG-873 fix it is the other way round. Cases that protect today's behaviour therefore call without `user_id` and have to gain `user_id=…` in the same change that fixes BUG-873 — this is an expected, one-line revision, not a design flaw.
- **`delete_account` R7 cases (G1):** give the account's invoices the account's own `workspace_id`, and use only the consistent states of the invoice table above. Insert invoices directly (never through the invoice manager).

## Not specified
- `AccountManager.__init__` — wires collaborators, no logic
- `create_account`: the `hasattr(account_data, 'tag_ids')` fallback (`app/managers/account_manager.py:57`) — dead code, to be removed (reviewer; Q11)
- `update_account`: the `hasattr(account_data, 'tag_ids')` part of the tag-ids check (`app/managers/account_manager.py:151`) — dead code, to be removed (reviewer; Q11)

---

## `AccountManager.create_account(session, account_data, workspace_id, user_id, ip_address=None, user_agent=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public

**Purpose:** Create an account in a workspace, attach the requested tags and record the creation in the audit log.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_data` | `AccountCreate` | `name` required, 1–255 chars (not trimmed today — R2); `account_code` ≤ 50; `primary_contact_person` / `secondary_contact_person` ≤ 255; `primary_email` / `secondary_email` ≤ 255, no format check today (R12); `primary_phone` / `secondary_phone` ≤ 50; `address`, `payment_preferences`, `bank_details` free text; `city`, `country` ≤ 100; `postal_code` ≤ 20; `allow_invoices` bool, default `True`; `tag_ids` list of ints, default `[]`. All optional fields default to `None`. Unknown fields are ignored by the schema. |
| `workspace_id` | int | Workspace the account is created in; not checked to exist (foreign key only). |
| `user_id` | int | Acting user; stored as `created_by`, `assigned_by`, `performed_by`. |
| `ip_address`, `user_agent` | str or None | *(requires new parameters — BUG-140)* client IP / user agent written to the audit row; default `None`. |

**Returns:** the new `Account`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** One account row is created with `name`, `account_code`, `primary_contact_person`, `primary_email`, `primary_phone`, `secondary_contact_person`, `secondary_email`, `secondary_phone`, `address`, `city`, `country`, `postal_code`, `payment_preferences`, `bank_details` and `allow_invoices` exactly as sent; optional fields not sent are `NULL`; `allow_invoices` not sent is `True`.
- **R2.** [BUG-860] [HR-1] The name is stored with leading/trailing whitespace removed; a blank or whitespace-only name is rejected by `AccountCreate` (422 / Pydantic `ValidationError`) and nothing is written. Inner whitespace and case are kept. *(Today: stored as typed; `"   "` is accepted. `""` is already rejected by the schema. Fix in `app/schemas/account.py`.)*
- **R3.** System fields: `workspace_id` = the argument, `created_by` = `user_id`, `is_active = True`, `is_deleted = False`, `created_at` set by the database; `updated_at`, `updated_by`, `deleted_at`, `deleted_by` are `NULL`.
- **R4.** The account is flushed, not committed.
- **R5.** With `tag_ids` empty (the default) no tag assignment is created and no usage count changes.
- **R6.** With `tag_ids` non-empty and every id valid, tags are attached following `_assign_tags_to_account` R3–R5, with `assigned_by = user_id`.
- **R6a.** [BUG-871] A `tag_ids` id that does not exist in the workspace rejects the create: `ValueError("Account tag {id} not found")`; nothing is written (no account, assignment, usage change or audit row). *(Today: the id is skipped silently and the create succeeds.)*
- **R6b.** [BUG-2987] A `tag_ids` id of an inactive (deleted) tag rejects the create: `ValueError("Account tag {id} is not active")`; nothing written. *(Today: attached like an active tag.)*
- **R8.** Exactly one audit row is written: `action_type = 'created'`, `description = "Account '<name>' created"` (name as stored), `performed_by = user_id`, `performed_at = utcnow()`.
- **R9.** [BUG-872] The audit row's `changes` is `{"after": <full snapshot>}` (see Facts) holding the stored values (`null` when not set) and the ids of the attached tags. There is no `"before"` key. *(Today: only `name`, `primary_contact_person`, `primary_email`, `address`, `city`, `country`; no tags.)*
- **R10.** [BUG-140] The audit row's `ip_address` and `user_agent` are the values passed in (client IP as resolved by trusted-proxy handling; `NULL` when not passed). *(Today: always `NULL`; requires new `ip_address` / `user_agent` parameters through endpoint → service → manager.)*
- **R11.** ✅ [Q5] No name uniqueness is checked: an account with the same `name` as another live account of the workspace is created normally.
- **R11a.** [BUG-874] A non-empty `account_code` equal (trimmed, case-insensitive) to the code of another live account of the workspace is rejected: `ValueError("Account code '{code}' already exists")`, where `{code}` is the code that was sent with leading/trailing whitespace removed and its case as typed (sending `" sup-001 "` against a stored `SUP-001` gives `Account code 'sup-001' already exists`). Nothing is written. Soft-deleted accounts do not count; codes of other workspaces do not count. The service answers 409 (integration-only). The database backs this with a partial unique index on `(workspace_id, lower(btrim(account_code)))` over rows that are not soft-deleted and whose trimmed code is not empty, so a direct insert of a second live row with the same code in any case / padding fails with `IntegrityError`. (Exception type and wording are a best-practice default, delegated by reviewer: the manager's existing `ValueError` convention, and the wording of the existing tag error `Tag with code '…' already exists`.) *(Today: duplicates created normally; no index.)*
- **R11b.** [BUG-874] The code is stored trimmed, case kept as typed (`"  Sup-001 "` is stored as `Sup-001`). A code that is empty after trimming (`""` or whitespace-only) is "no code": it is stored as `NULL` and never conflicts with anything, however many accounts have none. (Best-practice default, delegated by reviewer — the stored value is the value the uniqueness is checked on. Assert on the stored row; whether the schema or the manager normalises is the implementer's choice.) *(Today: stored exactly as typed, including `""` and `"   "`.)*
- **R12.** [BUG-875] `primary_email` and `secondary_email` are trimmed and must be valid email addresses; otherwise `AccountCreate` rejects the input (422 / `ValidationError`) and nothing is written. *(Today: stored as typed, whatever the text. Fix in `app/schemas/account.py`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Unknown / other-workspace tag id in `tag_ids` (intended, BUG-871) | `ValueError` | `Account tag {id} not found` |
| Inactive tag id in `tag_ids` (intended, BUG-2987) | `ValueError` | `Account tag {id} is not active` |
| Duplicate non-empty `account_code` (intended, BUG-874) | `ValueError` (409 at the API) | `Account code '{code}' already exists` (`{code}` = sent code, trimmed, case as typed) |

**Side effects:** 1 `accounts` row; 0..n `account_tag_assignments` rows and matching `usage_count` increments; 1 `financial_audit_logs` row; all flushed, nothing committed.

---

## `AccountManager.update_account(session, account_id, account_data, workspace_id, user_id, ip_address=None, user_agent=None)`
**Shape:** update
**Persistence:** writes
**Visibility:** public

**Purpose:** Change an account's details and, optionally, replace its set of tags, recording the change in the audit log.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_id` | int | Account to change. |
| `account_data` | `AccountUpdate` | Every field optional: same fields and length limits as `AccountCreate` (`name` 1–255 when sent), plus `is_active` (bool) and `tag_ids` (list of ints or `None`). |
| `workspace_id` | int | Caller's workspace. |
| `user_id` | int | Acting user. |
| `ip_address`, `user_agent` | str or None | *(requires new parameters — BUG-140)* written to the audit row. |

**Returns:** the same `Account`, flushed, not committed.

**Rules:**
- **R1.** No account with that id → `ValueError("Account {account_id} not found")`; nothing is written.
- **R1a.** [BUG-2986] At the API the `ValueError` of R1 / R2 / R3 is answered 404 `Account with ID {account_id} not found`, never 500. *(Today: generic 500; fix in `AccountService.update_account`. Integration-only.)*
- **R2.** [BUG-440] The account belongs to another workspace → `ValueError("Account {account_id} not found")` — identical to R1; nothing is written. *(Today: `Account {account_id} does not belong to workspace {workspace_id}`.)*
- **R3.** [BUG-863] [HR-4] A soft-deleted account is treated as not found: `ValueError("Account {account_id} not found")`, nothing written. *(Today: it is updated like a live account, including `is_active: true`.)*
- **R4.** Each of these fields that is sent with a non-null value is stored as sent: `name`, `account_code`, `primary_contact_person`, `primary_email`, `primary_phone`, `secondary_contact_person`, `secondary_email`, `secondary_phone`, `address`, `city`, `country`, `postal_code`, `payment_preferences`, `bank_details`, `allow_invoices`, `is_active`. Fields not sent keep their value. `allow_invoices: false` and `is_active: false` are stored (they are not treated as "not sent").
- **R4a.** [BUG-875] A sent `primary_email` / `secondary_email` is trimmed and must be a valid email address; otherwise `AccountUpdate` rejects the input (422), nothing written. *(Today: stored as typed. Fix in `app/schemas/account.py`.)*
- **R5.** [BUG-608] A nullable field sent as explicit `null` is cleared (stored `NULL`): `account_code`, `primary_contact_person`, `primary_email`, `primary_phone`, `secondary_contact_person`, `secondary_email`, `secondary_phone`, `address`, `city`, `country`, `postal_code`, `payment_preferences`, `bank_details`. `null` for `name`, `allow_invoices` or `is_active` is rejected by `AccountUpdate` with 422, nothing written. Omitted fields stay unchanged. *(Today: explicit `null` is ignored and the old value stays. Fix: `exclude_unset` only, not `exclude_none`, plus schema validation; in `app/schemas/account.py` and the manager.)*
- **R6.** [BUG-860] [HR-1] A sent name is stored trimmed; a whitespace-only name is rejected by `AccountUpdate` (422), nothing written. *(Today: stored as typed; `"   "` accepted. `""` is already rejected.)*
- **R7.** `is_active` can be switched off and on here; an inactive account is still returned by `get_account` (`get_account` R5), and by `search_accounts` only with `include_inactive=True` (`search_accounts` R1, R1a).
- **R8.** [BUG-869] [HR-9] `updated_by` is set to `user_id` only when at least one field value or the tag set actually changes. *(Today: set on every successful call.)*
- **R9.** Whenever the account row is actually changed, the database sets `updated_at` to the current time.
- **R10.** `tag_ids` not sent, or sent as `null` → the account's tags are not touched.
- **R11.** `tag_ids` sent as a list and every id valid → afterwards the account's tags are exactly the distinct ids of the list (`_assign_tags_to_account` R3–R5 decide the attaching). `tag_ids: []` removes all tags. Links to deleted (inactive) tags that are not in the list are the exception — see R13a.
- **R11a.** [BUG-2987] A tag id being newly added that is inactive rejects the update: `ValueError("Account tag {id} is not active")`, nothing written (tags already assigned and staying are not rechecked). *(Today: attached like an active tag.)*
- **R12.** Each tag that is removed has its `usage_count` lowered by 1 (never below 0); each tag that is newly attached has it raised by 1. (Only active tags are removed by a save — R13a.)
- **R13.** [BUG-870] [HR-9] A tag that was assigned before and is still in the list keeps its assignment row unchanged (same `id`, `assigned_at`, `assigned_by`) and its `usage_count` unchanged; only removed tags are deleted and only new tags added. *(Today: every existing assignment is deleted and re-created — new row, `assigned_at` = now, `assigned_by = user_id`; the count goes −1 then +1, and a tag whose count was already 0 ends at 1.)*
- **R13a.** [BUG-1487] A link of the account to a deleted (inactive) tag that is not in the list survives the save untouched: the assignment row stays (same `id`, `assigned_at`, `assigned_by`) and that tag's `usage_count` is unchanged. It stays hidden while the tag is deleted (`get_tags_for_account` R4) and shows again once the tag is restored ("hidden, not cascaded", per BUG-935). This holds for `tag_ids: []` too. Links to active tags that are not in the list are still removed (R11, R12). *(Today: every link is deleted, including links to deleted tags, and each deleted tag's `usage_count` is lowered by 1. Fix in `update_account`, together with BUG-870.)*
- **R14.** [BUG-871] A `tag_ids` id that does not exist in the workspace rejects the whole update: `ValueError("Account tag {id} not found")`; nothing written — the account's existing tags and every other field stay as they were. *(Today: the id is ignored without error, after the previous tags were already removed: `tag_ids: [999]` leaves the account with no tags and the call succeeds.)*
- **R15.** [BUG-632] An audit row is written only when at least one field or the tag set actually changed value: `action_type = 'updated'`, `performed_by = user_id`, `performed_at = utcnow()`. With no change, no audit row is written. *(Today: exactly one row on every successful call, even when nothing changed.)*
- **R16.** [BUG-872] Its `changes` is `{"before": <full snapshot>, "after": <full snapshot>}` (see Facts), all keys always present, with the values before and after the update, including the sorted tag ids. *(Today: only `name`, `primary_contact_person`, `primary_email`, `address`, `city`, `country`, `payment_preferences`, `allow_invoices`; no tag information.)*
- **R17.** Its `description` is `"Account '<name>' updated"` using the name **after** the update.
- **R18.** [BUG-140] Its `ip_address` and `user_agent` are the values passed in (`NULL` when not passed). *(Today: always `NULL`.)*
- **R19.** The account is flushed, not committed.
- **R20.** ✅ [Q5] No name uniqueness is checked: renaming to another live account's name succeeds.
- **R20a.** [BUG-874] Setting a non-empty `account_code` equal (trimmed, case-insensitive) to another live account's code of the workspace is rejected with the same error as `create_account` R11a — `ValueError("Account code '{code}' already exists")`, `{code}` = the sent code trimmed, case as typed (409 at the API, integration-only); nothing written — every field of the account, its tags and `updated_by` stay as they were and no audit row is written. An account keeping its own code (also when re-sent in another case or with padding) is not a conflict; soft-deleted accounts and other workspaces do not count. *(Today: succeeds.)*
- **R20b.** [BUG-874] A sent code is stored trimmed, case kept as typed; a sent code that is empty after trimming (`""` or whitespace-only) clears the code (stored `NULL`) and never conflicts — same normalisation as `create_account` R11b (best-practice default, delegated by reviewer). *(Today: stored exactly as typed, including `""` and `"   "`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Account id does not exist | `ValueError` | `Account {account_id} not found` |
| Account in another workspace (intended, BUG-440) | `ValueError` | `Account {account_id} not found` |
| Account soft-deleted (intended, HR-4) | `ValueError` | `Account {account_id} not found` |
| Unknown / other-workspace tag id in `tag_ids` (intended, BUG-871) | `ValueError` | `Account tag {id} not found` |
| Newly added tag inactive (intended, BUG-2987) | `ValueError` | `Account tag {id} is not active` |
| Duplicate non-empty `account_code` (intended, BUG-874) | `ValueError` (409 at the API) | `Account code '{code}' already exists` (`{code}` = sent code, trimmed, case as typed) |

**Side effects:** `accounts` row updated (sent fields, `updated_by`, `updated_at`); tag assignments of active tags deleted / created and `usage_count` adjusted when `tag_ids` is a list (links to deleted tags untouched — R13a); 0..1 `financial_audit_logs` row (none when nothing changed); all flushed.

---

## `AccountManager.get_account(session, account_id, workspace_id, include_deleted=False)`
**Shape:** get
**Persistence:** reads
**Visibility:** public

**Purpose:** Fetch one account of the caller's workspace by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_id` | int | Account id. |
| `workspace_id` | int | Caller's workspace. |
| `include_deleted` | bool, default `False` | *(requires new parameter — BUG-862)* when `True` a soft-deleted account is returned. |

**Returns:** the `Account`, or `None`. Never raises.

**Rules:**
- **R1.** A live account of the workspace is returned.
- **R2.** No account with that id → `None`.
- **R3.** The account belongs to another workspace → `None` (same result as not existing).
- **R4.** [BUG-862] [HR-4] A soft-deleted account → `None` by default (404 at the API); with `include_deleted=True` it is returned. *(Today: always returned; requires new parameter `include_deleted`.)*
- **R5.** An inactive (`is_active = False`) but not deleted account is returned.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| (none) | — | — |

**Side effects:** none

---

## `AccountManager.search_accounts(session, workspace_id, name=None, tag_code=None, skip=0, limit=100, include_inactive=False)`
**Shape:** search
**Persistence:** reads
**Visibility:** public

**Purpose:** List the workspace's accounts (active by default), optionally filtered by name text and/or by tag code, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | Caller's workspace. |
| `name` | str or None | Search text for the account name. Not trimmed today (R5). |
| `tag_code` | str or None | Tag code (e.g. `supplier`). |
| `skip` | int, default 0 | Rows to skip. Not validated here (endpoint requires ≥ 0). |
| `limit` | int, default 100 | Page size. No bounds here (endpoint: ≤ 500, no minimum today — R13). |
| `include_inactive` | bool, default `False` | *(requires new parameter — BUG-878)* when `True`, inactive not-deleted accounts are returned too. |

**Returns:** list of `Account` (possibly empty).

**Rules:**
- **R1.** By default only accounts of `workspace_id` that are active (`is_active = True`) and not soft-deleted are returned. Inactive accounts are left out, deleted accounts and accounts of other workspaces never appear.
- **R1a.** [BUG-878] With `include_inactive=True` inactive, not-deleted accounts of the workspace are also returned; deleted accounts and other workspaces' accounts still never appear. The option is reachable from `GET /accounts/`. *(Today: no such option; inactive accounts can never be listed.)*
- **R2.** `name` `None`, `""` or whitespace-only after trimming → no name filter.
- **R3.** `name` given (non-blank) → only accounts whose name contains the text, case-insensitively, anywhere in the name.
- **R4.** [BUG-868] [HR-8] `%`, `_` and `\` in the text match literally. *(Today: `%` and `_` act as wildcards; `%` alone matches every account. `\` acts as the `LIKE` escape character: it does not match a backslash in the name but makes the next pattern character literal — searching `\` alone finds only names ending in `%`, so an account named `Acme\Ltd` is not found; see Facts.)*
- **R5.** [BUG-637] The search text is trimmed: `" acme "` matches "Acme Ltd"; a whitespace-only text means no name filter (R2). *(Today: used as typed — `"   "` only matches names containing three consecutive spaces; `" acme "` does not match "Acme Ltd".)*
- **R6.** `tag_code` `None` or `""` → no tag filter.
- **R7.** `tag_code` given → only accounts that have at least one tag assignment (recorded in this workspace) to a tag with that code. An account matching through several assignments appears once.
- **R8.** [BUG-861] [HR-3] The tag code is compared after trimming, case-insensitively. *(Today: exact, case-sensitive match.)*
- **R9.** [BUG-864] [HR-4] Only active tags match; an assignment to a deleted (inactive) tag does not make the account match. *(Today: inactive tags match.)*
- **R10.** With both `name` and `tag_code`, an account must satisfy both.
- **R11.** [BUG-866] [HR-6] Results are ordered by name case-insensitively ascending, then `id` ascending. *(Today: no order — the rows come back in an undefined, plan-dependent order; see Notes for the test designer.)*
- **R12.** `skip` and `limit` are applied after all filters (and after ordering): `skip` matching rows are left out, at most `limit` returned. Defaults are 0 and 100. A page is short only when there are no more matches.
- **R13.** [BUG-867] [HR-7] `limit` must be at least 1 (422 at `GET /accounts/`). *(Today: `limit = 0` returns `[]`; a negative `limit` fails with a database error. Fix in the endpoint; integration-only.)*
- **R14.** No match → `[]`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| (none raised by this method) | — | — |

**Side effects:** none

---

## `AccountManager.delete_account(session, account_id, workspace_id, user_id, ip_address=None, user_agent=None)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public

**Purpose:** Soft-delete an account and record the deletion in the audit log.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_id` | int | Account to delete. |
| `workspace_id` | int | Caller's workspace. |
| `user_id` | int | Acting user. |
| `ip_address`, `user_agent` | str or None | *(requires new parameters — BUG-140)* written to the audit row. |

**Returns:** the `Account`, flushed, not committed.

**Rules:**
- **R1.** No account with that id → `ValueError("Account {account_id} not found")`; nothing written.
- **R1a.** [BUG-2986] At the API the `ValueError` of R1 / R2 is answered 404 `Account with ID {account_id} not found` and R3 ("already deleted") is answered 400, never 500; the open-invoices refusal (R7) is answered 400. *(Today: generic 500; fix in `AccountService.delete_account`. Integration-only.)*
- **R2.** [BUG-440] The account belongs to another workspace → `ValueError("Account {account_id} not found")` — identical to R1; nothing written. *(Today: `Account {account_id} does not belong to workspace {workspace_id}`.)*
- **R3.** The account is already soft-deleted → `ValueError("Account {account_id} is already deleted")`; `deleted_at` / `deleted_by` stay as they were and no audit row is written.
- **R4.** Otherwise the account gets `is_deleted = True`, `is_active = False`, `deleted_at = utcnow()`, `deleted_by = user_id`. `updated_by` is not changed; the database sets `updated_at`. All other fields keep their values.
- **R5.** [BUG-872] Exactly one audit row is written: `action_type = 'deleted'`, `description = "Account '<name>' deleted"`, `performed_by = user_id`, `performed_at = utcnow()`, `changes = {"before": <full snapshot>}` (see Facts) of the account including its tag ids; no `"after"` key. *(Today: only `name`, `primary_contact_person`, `primary_email`.)*
- **R6.** [BUG-877] The account's tag assignment rows stay, and each assigned tag's `usage_count` is lowered by 1 (never below 0). *(Today: no `usage_count` changes.)*
- **R7.** [BUG-876] An account that has at least one open invoice (R7a) cannot be deleted: `ValueError("Account has open invoices — settle or void them first")` (the dash is an em dash, U+2014; 400 at the API). Nothing is changed: the account row stays exactly as it was (`is_deleted False`, `is_active`, `deleted_at`, `deleted_by`, `updated_by` untouched), no audit row is written, no tag `usage_count` changes, and the invoices are not touched. One open invoice is enough, whatever the account's other invoices are. *(Today: invoices are never looked at; the account is deleted like any other.)*
- **R7a.** [BUG-876] "Open invoice" means a row of `account_invoices` with `account_id` = this account whose `invoice_status` is `'draft'` (whatever its amounts), or whose `invoice_status` is `'confirmed'` and which still has a balance to pay — `payment_status` `'unpaid'` or `'partial'`, i.e. `paid_amount < invoice_amount`. Both invoice types (`'payable'` and `'receivable'`) count the same. See the invoice state table in Facts. (Definition is a best-practice default, delegated by reviewer; it follows the reviewer's answer to Q7.) *(Today: no such check.)*
- **R7b.** An account can be deleted (R4) when it has no invoices at all, or when every one of its invoices is voided (`invoice_status = 'voided'`) or confirmed and fully paid (`payment_status = 'paid'`). Its invoices are left exactly as they were. Open invoices of *other* accounts never block the deletion.
- **R7c.** The checks of R1, R2 and R3 come first: a missing, other-workspace or already-deleted account gets its own error (R1–R3) even when it has open invoices; the open-invoices error is only raised for a live account of the caller's workspace. (Order is a best-practice default, delegated by reviewer: existence and state are established before dependents are examined, so nothing about another workspace's invoices can leak.)
- **R7d.** No row lock is taken for the invoice check: HR-10 does not apply to `delete_account`. HR-10 itself excludes plain soft deletes; the deletion moves no money and loses no data (the invoice and its balance stay intact and visible in the invoice screens, and the account can be restored), and a lock on the account row alone could not stop an invoice being created at the same moment. Nothing to test here. (Best-practice default, delegated by reviewer.)
- **R8.** An inactive (not deleted) account can be deleted.
- **R9.** The account is flushed, not committed.
- **R10.** [BUG-140] The audit row's `ip_address` and `user_agent` are the values passed in (`NULL` when not passed). *(Today: always `NULL`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Account id does not exist | `ValueError` | `Account {account_id} not found` |
| Account in another workspace (intended, BUG-440) | `ValueError` | `Account {account_id} not found` |
| Already soft-deleted | `ValueError` | `Account {account_id} is already deleted` |
| Live account of the workspace with an open invoice — R7a (intended, BUG-876) | `ValueError` | `Account has open invoices — settle or void them first` |

**Side effects:** `accounts` row: `is_deleted`, `is_active`, `deleted_at`, `deleted_by` (+ `updated_at` by the database); tag `usage_count` − 1 (floor 0) per assigned tag; 1 `financial_audit_logs` row; flushed. `account_invoices` is only read (intended, BUG-876), never written. None of this when the deletion is refused.

---

## `AccountManager._assign_tags_to_account(session, account_id, tag_ids, workspace_id, user_id)`
**Shape:** helper
**Persistence:** writes
**Visibility:** internal (used by: `create_account`, `update_account`)

**Purpose:** Attach a list of tags to an account, rejecting the whole list when any tag cannot be attached.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_id` | int | Account to tag; not checked here (callers have already loaded it). |
| `tag_ids` | list of int | Tag ids to attach; may be empty, may repeat. |
| `workspace_id` | int | Caller's workspace. |
| `user_id` | int | Stored as `assigned_by`. |

**Returns:** `None`.

**Rules:**
- **R1.** Empty list → nothing is written.
- **R2.** [BUG-871] A tag id that does not exist, or belongs to another workspace, raises `ValueError("Account tag {id} not found")` and nothing is written. *(Today: skipped without error.)*
- **R3.** A tag already assigned to the account is skipped: no second assignment, `usage_count` unchanged.
- **R4.** Otherwise one assignment row is created (`account_id`, `tag_id`, `workspace_id`, `assigned_by = user_id`, `assigned_at` = current time) and that tag's `usage_count` rises by 1.
- **R5.** The same id twice in the list results in one assignment and one increment.
- **R6.** [BUG-2987] A tag that is not already assigned and is inactive (deleted) raises `ValueError("Account tag {id} is not active")` and nothing is written. *(Today: attached exactly like an active tag.)*
- **R7.** [BUG-871] All ids are validated (R2, R6) before any assignment is written: if any id is rejected, no assignment is created and no `usage_count` changes — valid ids in the same list are not attached. *(Today: each id is handled independently and valid ids are attached while others are skipped.)*
- **R8.** Everything is flushed, nothing committed.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Tag missing / other workspace (intended) | `ValueError` | `Account tag {id} not found` |
| Tag inactive and not yet assigned (intended) | `ValueError` | `Account tag {id} is not active` |

**Side effects:** `account_tag_assignments` rows created; `account_tags.usage_count` incremented; flushed.

---

## `AccountManager.assign_tag(session, account_id, tag_id, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public

**Purpose:** Attach one tag to one account; doing it twice is harmless.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_id` | int | Account to tag. |
| `tag_id` | int | Tag to attach. |
| `workspace_id` | int | Caller's workspace. |
| `user_id` | int | Stored as `assigned_by` (and, intended, `updated_by` / `performed_by`). |

**Returns:** `None`.

**Rules:**
- **R1.** No account with that id → `ValueError("Account {account_id} not found")`.
- **R2.** The account belongs to another workspace → the same `ValueError("Account {account_id} not found")`.
- **R3.** [BUG-863] [HR-4] A soft-deleted account → `ValueError("Account {account_id} not found")`, nothing written. *(Today: accepted.)*
- **R4.** The tag does not exist or belongs to another workspace → `ValueError("Account tag {tag_id} not found")`. The account is checked first: when both are wrong, the account error is raised.
- **R5.** The tag is inactive → `ValueError("Account tag {tag_id} is not active")` — also when that tag is already assigned to the account.
- **R6.** The (active) tag is already assigned → returns `None` and nothing changes: no second assignment, `usage_count` unchanged, the existing `assigned_at` / `assigned_by` kept, no audit row, `updated_by` unchanged.
- **R7.** Otherwise one assignment row is created (`account_id`, `tag_id`, `workspace_id`, `assigned_by = user_id`, `assigned_at` = current time) and the tag's `usage_count` rises by 1; flushed, not committed.
- **R8.** [BUG-873] A real assignment (R7) also writes one `account` audit row: `action_type = 'updated'`, `description = "Account '<name>' updated"`, `performed_by = user_id`, `performed_at = utcnow()`, `changes = {"before": {"tag_ids": [...]}, "after": {"tag_ids": [...]}}` (sorted ascending, before / after the assignment), and sets the account's `updated_by = user_id` (the database sets `updated_at`). The audit description form is a best-practice default, delegated by reviewer. *(Today: no audit row, `updated_by` / `updated_at` untouched.)*
- **R9.** An inactive (not deleted) account can be tagged.
- **R10.** The database also forbids a second row for the same `(account_id, tag_id)` (unique constraint `uq_account_tag`).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Account missing / other workspace / soft-deleted (intended, HR-4) | `ValueError` | `Account {account_id} not found` |
| Tag missing / other workspace | `ValueError` | `Account tag {tag_id} not found` |
| Tag inactive | `ValueError` | `Account tag {tag_id} is not active` |

**Side effects:** 1 `account_tag_assignments` row; tag `usage_count` + 1; 1 audit row and `updated_by` stamp (intended, BUG-873); flushed. None when already assigned.

---

## `AccountManager.unassign_tag(session, account_id, tag_id, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public

**Purpose:** Remove one tag from one account.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_id` | int | Account. |
| `tag_id` | int | Tag to remove; not looked up as a tag, only as an assignment. |
| `workspace_id` | int | Caller's workspace. |
| `user_id` | int, **required** | *(requires new parameter — BUG-873)* acting user for the audit row / `updated_by`. Required, with no default, placed after `workspace_id` exactly as in `assign_tag`; `None` is not a valid value (best-practice default, delegated by reviewer: an audited change always has an actor, and the two sibling methods keep the same signature). Today the parameter does not exist — passing it raises `TypeError`. |

**Returns:** `None`.

**Rules:**
- **R1.** No account with that id → `ValueError("Account {account_id} not found")`.
- **R2.** The account belongs to another workspace → the same `ValueError("Account {account_id} not found")`.
- **R3.** [BUG-863] [HR-4] A soft-deleted account → `ValueError("Account {account_id} not found")`, nothing written. *(Today: accepted.)*
- **R4.** [BUG-879] The tag is not assigned to the account in this workspace — including a tag id that does not exist or belongs to another workspace — → `ValueError("Tag {tag_id} assignment not found for account {account_id}")` (404 at the API through the service's existing "not found" translation); nothing changes. *(Today: message `Tag {tag_id} is not assigned to account {account_id}`, which the service answers as 422 instead of the documented 404.)*
- **R5.** Otherwise the assignment row is deleted and the tag's `usage_count` falls by 1, but never below 0 (a count already at 0 stays 0); flushed, not committed.
- **R6.** An inactive (deleted) tag can be removed from an account.
- **R7.** [BUG-873] A real removal (R5) also writes one `account` audit row (`action_type = 'updated'`, `description = "Account '<name>' updated"`, `performed_by = user_id`, `changes = {"before": {"tag_ids": [...]}, "after": {"tag_ids": [...]}}`, sorted ascending) and sets the account's `updated_by = user_id` (the database sets `updated_at`). *(Today: no audit row, `updated_by` / `updated_at` untouched.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Account missing / other workspace / soft-deleted (intended, HR-4) | `ValueError` | `Account {account_id} not found` |
| Tag not assigned (intended, BUG-879) | `ValueError` | `Tag {tag_id} assignment not found for account {account_id}` |

**Side effects:** 1 `account_tag_assignments` row deleted; tag `usage_count` − 1 (floor 0); 1 audit row and `updated_by` stamp (intended, BUG-873); flushed.

---

## `AccountManager.get_tags_for_account(session, account_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** List the tags attached to an account.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `account_id` | int | Account id; the account itself is not looked up. |
| `workspace_id` | int | Caller's workspace. |

**Returns:** list of `AccountTag` objects (possibly empty). Not paged.

**Rules:**
- **R1.** Returns every tag that has an assignment to `account_id` recorded in `workspace_id`, each tag once.
- **R2.** An account with no tags, or an `account_id` that does not exist → `[]`.
- **R3.** Assignments recorded under another workspace are not returned: asking with a different `workspace_id` gives `[]`.
- **R4.** [BUG-865] [HR-4] Only active tags are returned. *(Today: inactive (deleted) tags are returned too.)*
- **R5.** [BUG-1486] [HR-6] Tags are ordered by name case-insensitively ascending, then `id` ascending; system tags (`is_system_tag = True`) are not grouped first — they take their place by name like any other tag. *(Today: no `ORDER BY` — no defined order; see Notes for the test designer.)*
- **R6.** The account's own state is not checked: the tags of a soft-deleted or inactive account are returned (all callers check the account first).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| (none) | — | — |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| `account_manager.py` 57 | input has `tag_ids` attribute / not — dead branch, to be removed (Q11) | `create_account` R5, R6 (attribute-less side removed) |
| `account_manager.py` 59–78 | fields copied, `allow_invoices` default, system fields | `create_account` R1, R3 |
| `account_manager.py` 84 | `tag_ids` empty / non-empty | `create_account` R5, R6 |
| `account_manager.py` 94–105 | audit row on create | `create_account` R8–R10 |
| `account_manager.py` 137 | account not found → raise | `update_account` R1 |
| `account_manager.py` 141 | other workspace → raise | `update_account` R2 |
| `account_manager.py` 136 (no `is_deleted` check) | soft-deleted account | `update_account` R3 |
| `account_manager.py` 151 | has `tag_ids` (dead part, Q11) and it is not `None` / else | `update_account` R10, R11 |
| `account_manager.py` 154 | `exclude_unset` / `exclude_none` | `update_account` R4, R5 |
| `account_manager.py` 156–164 | each known key present / absent | `update_account` R4 |
| `account_manager.py` 165 | `updated_by` always set | `update_account` R8 |
| `account_manager.py` 171 | `tag_ids is not None` | `update_account` R10, R11 |
| `account_manager.py` 177 | new list empty / non-empty | `update_account` R11, R14 |
| `account_manager.py` 192–201 | audit row on update | `update_account` R15–R18 |
| `account_manager.py` 226 | not found / other workspace / found | `get_account` R1–R3, R5 |
| `account_manager.py` 225 (no `is_deleted` check) | soft-deleted account | `get_account` R4 |
| `account_manager.py` 237–238 | default `skip` / `limit` | `search_accounts` R12, R13 |
| `account_manager.py` 276 | account not found → raise | `delete_account` R1 |
| `account_manager.py` 279 | other workspace → raise | `delete_account` R2 |
| `account_manager.py` 282 | already deleted → raise | `delete_account` R3 |
| `account_manager.py` 286–304 | audit row, then soft-delete fields | `delete_account` R4–R6, R10 |
| `account_manager.py` 282–286 (no invoice check) | account has open / only settled or voided / no invoices | `delete_account` R7, R7a–R7c |
| `account_manager.py` 327 | loop over zero / one / many tag ids | `_assign_tags_to_account` R1, R5, R7 |
| `account_manager.py` 330 | tag not in workspace → skip | `_assign_tags_to_account` R2 |
| `account_manager.py` 329 (no `is_active` check) | inactive tag | `_assign_tags_to_account` R6 |
| `account_manager.py` 334 | already assigned → skip | `_assign_tags_to_account` R3, R5 |
| `account_manager.py` 340–349 | create assignment, increment | `_assign_tags_to_account` R4 |
| `account_manager.py` 366 | account missing or other workspace → raise | `assign_tag` R1, R2 |
| `account_manager.py` 365 (no `is_deleted` check) | soft-deleted account | `assign_tag` R3 |
| `account_manager.py` 370 | tag not found → raise | `assign_tag` R4 |
| `account_manager.py` 372 | tag inactive → raise | `assign_tag` R5 |
| `account_manager.py` 375 | already assigned → return | `assign_tag` R6 |
| `account_manager.py` 380–387 | create assignment, increment | `assign_tag` R7, R8 |
| `account_manager.py` 403 | account missing or other workspace → raise | `unassign_tag` R1, R2 |
| `account_manager.py` 402 (no `is_deleted` check) | soft-deleted account | `unassign_tag` R3 |
| `account_manager.py` 409 | assignment not deleted → raise | `unassign_tag` R4 |
| `account_manager.py` 412 | decrement | `unassign_tag` R5, R7 |
| `dao/base.py` 43 | `get` by id only (no workspace, no soft-delete filter) | `update_account` R1–R3, `get_account` R2–R4, `delete_account` R1–R3 |
| `dao/base.py` 76 | create from dict / schema (always dict here) | `create_account` R1, `_assign_tags_to_account` R4 |
| `dao/base.py` 108 | update from dict / schema (always dict here) | `update_account` R4, `delete_account` R4 |
| `dao/base.py` 114 | only existing attributes are set (always true here) | `update_account` R4 |
| `dao/base.py` 187–194 | tag looked up by id and workspace | `_assign_tags_to_account` R2, `assign_tag` R4 |
| `dao/account.py` 68–72 | workspace / active / not-deleted filter | `search_accounts` R1, R1a |
| `dao/account.py` 74 | `name` falsy / given | `search_accounts` R2–R5 |
| `dao/account.py` 77 | `tag_code` falsy / given | `search_accounts` R6–R9 |
| `dao/account.py` 87 | distinct, offset, limit, no order | `search_accounts` R7, R11–R13 |
| `dao/account_tag.py` 99 | increment only when tag found | `_assign_tags_to_account` R4, `assign_tag` R7 |
| `dao/account_tag.py` 119 | decrement only when tag found and count > 0 | `unassign_tag` R5, `update_account` R12, `delete_account` R6 |
| `dao/account_tag_assignment.py` 39–47 | tags of an account, workspace-scoped, no order, no active filter | `get_tags_for_account` R1–R5 |
| `dao/account_tag_assignment.py` 64–72, 92 | assignment exists (workspace-scoped) | `_assign_tags_to_account` R3, `assign_tag` R6 |
| `dao/account_tag_assignment.py` 112 | assignment found → delete / not found → `False` | `unassign_tag` R4, R5 |
| `dao/account_tag_assignment.py` 133–148 | remove all assignments (zero / many), decrement each — also links to inactive tags | `update_account` R11–R13, R13a |
| `utils/audit_logger.py` 104 | `None` audit values omitted (ip, user agent, related entity) | `create_account` R10, `update_account` R18, `delete_account` R10 |
| `utils/audit_logger.py` 130, 132 | `before` / `after` key only when given | `create_account` R9, `update_account` R16, `delete_account` R5 |
| `utils/audit_logger.py` 156–175 | listed fields copied (plain values kept as-is) | `create_account` R9, `update_account` R16, `delete_account` R5 |

## Gap log
- G1 (`account_manager.cases.md` gap 1) — Fact + Intent (best-practice default, delegated by reviewer) — added the invoice facts to Facts (table `account_invoices` / model `AccountInvoice`, mandatory columns, status values, the five consistent states and which of them block deletion). `delete_account` R7 now states exactly what "nothing changed" covers; new R7a (definition of an open invoice: draft, or confirmed with `payment_status` unpaid / partial; both invoice types), R7b (no invoices / only settled or voided invoices / other accounts' invoices do not block — works today, untagged), R7c (R1–R3 are checked before the invoice check). Errors row, Side effects, Q7 Resolution and Branch map updated. Same bug BUG-876, no new ID. Unblocks the three R7 cases.
- G2 (gap 2) — Intent (best-practice default, delegated by reviewer) — duplicate code raises `ValueError("Account code '{code}' already exists")` with `{code}` = sent code trimmed, case as typed (`create_account` R11a, `update_account` R20a, both Errors tables); the index is spelled out. New `create_account` R11b / `update_account` R20b: the code is stored trimmed, case kept; empty or whitespace-only means "no code" (stored `NULL`, never conflicts). Q4 Resolution updated. Same bug BUG-874 (same fix), no new ID.
- G3 (gap 3) — Intent (best-practice default, delegated by reviewer) — `unassign_tag` `user_id` is required, no default, after `workspace_id` as in `assign_tag` (Inputs). Note added for the test designer on revising today's-signature cases when BUG-873 is fixed.
- G4 (gap 4) — Fact — added the `account_tags` columns (the code column is `tag_code`, not `code`) and that the table has no unique or check constraint on `name` / `tag_code`: two tags with the same code, or names differing only in case, can be inserted directly. `search_accounts` R7 "appears once" and `get_tags_for_account` R5 "then `id`" are testable as designed.
- G5 (gap 5) — Fact — today `\` in the search text is the `LIKE` escape character (verified on the test database): searching `\` finds only names ending in `%`, so `Acme\Ltd` is not found. Added to Facts and to the `Today:` note of `search_accounts` R4. The expected-to-fail assumption of the backslash case holds.
- G6 (gap 6) — Fact — `AccountManager()` takes no arguments; module instance `account_manager` (Facts).
- G7 (gap 7) — Test mechanics — today's order is undefined and plan-dependent (hash order for `search_accounts`, physical tag-row order for `get_tags_for_account`); note added on how to build ordering cases that cannot pass by accident. `Today:` notes of `search_accounts` R11 and `get_tags_for_account` R5 point to it.
- G8 (gap 8) — House rule checked, not applicable (best-practice default, delegated by reviewer) — HR-10 does not apply to `delete_account`: it is a plain soft delete, which HR-10 excludes, and it moves no money. Recorded as `delete_account` R7d; no lock, no lock case.
- C1 (2026-11-03, correction from the `account_tag_assignment` DAO describer, FU-1 (a)) — `get_tags_for_account` R5 and P7 cited BUG-719 (an inventory bug); now BUG-1486, the register row for this order. R5 gained BUG-1486's "system tags are not grouped first" clause and `[HR-6]`; the Notes for the test designer now say today's tag order is not reliably the insertion order. Not a gap; done by one agent, without a separate review round.
- C2 (2026-11-03, correction from the same describer, FU-1 (b)) — BUG-1487 added to `update_account`: new R13a (a link to a deleted tag that is not in the list survives a save, row and counter untouched); R11, R12, Side effects and Branch map point to it; precedent entry P9. FU-1 (c) (`delete_account` R6 and deleted tags' counters) was not part of this correction and is still open.
- C3 (2026-11-22, routed by the `account_service` verifier; decided under the reviewer's delegation) — P1 and P8 cited existing BUG-124 / BUG-629, whose rows describe other modules (same pattern, not the same bug). Opened BUG-2986 (P1) and BUG-2987 (P8) and re-tagged `update_account` R1a, `delete_account` R1a, `_assign_tags_to_account` R6, `create_account` R6b, `update_account` R11a. Behaviour unchanged.
