# Spec — `app/services/account_service.py`

> **Status:** APPROVED (apply-review 2026-11-21; every item decided by house rule, precedent, or Claude under the reviewer's delegation of 2026-11-21; no owner question)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/machine_item_service.spec.md`: this spec covers what the service adds — commit / rollback, which manager it calls, the translation of the manager's `ValueError`s into the application's HTTP errors, and the response dicts. The **Transaction contract TC1–TC6 is defined in `tests/unit/services/base_service.spec.md`** and cited here. Below the service: `tests/unit/managers/account_manager.spec.md` (APPROVED), `tests/unit/managers/account_invoice_manager.spec.md` (APPROVED; only `list_accounts_hub_page`), `tests/unit/dao/account.spec.md` (APPROVED; `get_accounts_by_tag_id`), `tests/unit/dao/account_tag.spec.md` (inherited `get_by_id_and_workspace`). Nothing the manager specs decide is asked again here.

> **Routed here and written as rules:** account manager P1 / R1a (BUG-2986: update / delete refusals answer 4xx, never 500), Q4 (BUG-874: duplicate code → 409), Q1 (BUG-871: unknown tag → 404), Q7 / R1a (BUG-876: open invoices → 400), Q10 (BUG-879: unassigned tag → 404 through the existing translation), Q3 (BUG-873: `unassign_tag` gains `user_id`), P3 (BUG-140: client IP / user agent passed through), Q9 (BUG-878: `include_inactive` reachable), HR-4 line (BUG-862: `include_deleted` on the get); account DAO FU-1 (a) → BUG-2982, FU-1 (b) → BUG-2983, FU-1 (c) → cited (BUG-865, BUG-1486).

> **Bug block:** BUG-2982 … BUG-3001. Used: BUG-2982 … BUG-2985, logged in `docs/testing/bugs.md` at apply-review (2026-11-21); BUG-2985 is a frontend note row (no backend test). BUG-2986 … BUG-3001 unused.

> **Deferred areas.** Production: not touched. Projects: not touched.

> **Verified by running** (`v_acc.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1desc\account_service\`, one outer transaction on `marker_test`, session with `join_transaction_mode="create_savepoint"`, rolled back; nothing persisted): `update_account` of a missing id raises `ValueError("Account 99999999 not found")` and of another workspace's account `ValueError("Account N does not belong to workspace W")` (both 500 at the API); `delete_account` of another workspace's account → `NotFoundError` 404 `Account with ID N not found`; deleting an already-deleted account → `ValueError("Account N is already deleted")`; `get_account_with_tags` and `get_account` return a soft-deleted account; `assign_tag` returns the dict with the new tag; `assign_tag` of a missing account → `NotFoundError` 404 `Account 99999999 not found`; of an inactive tag → `BusinessRuleError` 422 `Account tag N is not active`; `unassign_tag` of an unassigned tag → `BusinessRuleError` 422 `Tag N is not assigned to account M`; `create_account` with `tag_ids=[99999999]` succeeds; hub rollup of an account without invoices → `Decimal('0')`, `0`, `False`; `get_accounts_by_tag_id` lists the accounts of an inactive tag, `limit=0` → `[]`, another workspace's tag → `NotFoundError` 404 `Account tag N not found`. **Not run:** HTTP; the intended behaviour of any bug.

## Review
> Resolved at apply-review (2026-11-21). Every item is decided (house rule, precedent, or Claude under the reviewer's delegation of 2026-11-21); precedent matches confirmed under the same delegation.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-4 | "Accounts with tag N" answers 200 for a deleted tag | bug — BUG-2982 | house rule |
| HR-7 | `GET /accounts/by-tag/{id}/` accepts `limit` 0 or negative | bug — BUG-2983 | house rule |
| P1 | Editing a missing account, or deleting one twice, answers 500 | bug — BUG-2986 | precedent, account manager P1 |
| P2 | Refused account delete does not say which invoices block it | bug — BUG-2984 (+ frontend BUG-2985) | precedent, owner's refusal rule (BUG-948) |
| Q1 | Which manager refusals the service turns into which status | translate the listed refusals; nothing else | Claude, delegated |
| Q2 | Creating / updating with a deleted tag: which status? | 422, as `assign_tag` | Claude, delegated |
| Q3 | Deleting an already-deleted account once BUG-862 is fixed | stays 400 "already deleted" | Claude, delegated |
| Q4 | `update_account`'s "manager returned nothing" check can never fire | remove | Claude, delegated |
| Q5 | `get_account` has no caller | remove | Claude, delegated |

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-4** `get_accounts_by_tag_id` R2 — the tag is looked up with the raw by-id-and-workspace lookup, so a deleted tag (`account_tags.is_active = False`) passes: today the page lists that tag's accounts (verified), after BUG-1481 it would list nothing, with 200 either way. Intended: a deleted tag is "not found" — 404 `Account tag {tag_id} not found`, the same answer as a tag that does not exist (account DAO FU-1 (a)).
**Answer:** bug — per HR-4 (house rule) → 🐞 BUG-2982
**Resolution:** a deleted tag answers 404 `Account tag {tag_id} not found`. Rules: `get_accounts_by_tag_id` R2.
- **HR-7** `get_accounts_by_tag_id` R5 — `GET /accounts/by-tag/{tag_id}/` declares `limit` with `le=100` and no lower bound: `limit=0` returns `[]` (verified), a negative `limit` reaches Postgres as a `DataError`. Intended: `limit >= 1`, 422 otherwise (fix in the endpoint). Same root as BUG-867 (`GET /accounts/`).
**Answer:** bug — per HR-7 (house rule) → 🐞 BUG-2983
**Resolution:** `limit >= 1` at `GET /accounts/by-tag/{tag_id}/`, 422 otherwise (endpoint fix). Rules: `get_accounts_by_tag_id` R5.

Checked and **not** violated: **HR-1, HR-2, HR-3, HR-8, HR-9** — the service stores, compares, searches and stamps nothing itself; the manager's bugs (BUG-860, BUG-874, BUG-861, BUG-868, BUG-869, BUG-870) are reached through it and cited. **HR-5, HR-6** — every filter, order and page is the manager's / DAO's (BUG-866, BUG-1480, BUG-623, BUG-1486 cited); the service only maps the rows it gets, in the order it gets them. **HR-7** — `GET /accounts/hub/` enforces `1 ≤ limit ≤ 500`; `GET /accounts/` is BUG-867. **HR-10** — nothing here moves money or stock; the only state check (`delete_account`'s open invoices) is ruled lock-free by account manager R7d. **HR-11 … HR-14** — no external call, no batch. **HR-15** — no rounding: the hub money figures are database sums passed through. **HR-16** — an account or tag of another workspace gets the same 404 as a missing one (R-rules below); the blockers of BUG-2984 show another workspace's invoice only as one `{"type": "other_workspace"}` entry.

### Precedent matches — confirmed

### P1. Editing a missing account, or deleting an account twice, answers 500 — 🐞 BUG-2986
**Background:** The account manager reports these refusals as a plain Python `ValueError`. The service translates `ValueError` only on the two tag endpoints; on update and delete it is re-raised as it is, and the application has no handler for `ValueError`, so it becomes the generic 500.
**What happens today:** `PUT /accounts/{id}/` for an id that does not exist or belongs to another workspace → 500. `DELETE /accounts/{id}/` on an already-deleted account → 500. (Verified at the service.)
**Example:** A user has "Acme Ltd" open in two tabs, deletes it in one and presses Delete again in the other: "internal server error" instead of "already deleted".
**Rules affected:** `update_account` R3; `delete_account` R3
**Answer:** bug — per BUG-124 precedent (same pattern; logged for accounts as BUG-2986) (account manager P1, already ruled): not found / other workspace → 404 `Account with ID {account_id} not found`; already deleted → 400; the service translates after the rollback (precedent — confirmed under the reviewer's delegation, 2026-11-21)
**Resolution:** BUG-2986 (opened 2026-11-22; first cited as BUG-2986); its service side is `update_account` R3 and `delete_account` R3.

### P2. A refused account delete does not say which invoices block it — 🐞 BUG-2984, frontend 🐞 BUG-2985
**Background:** Account manager Q7 (BUG-876, reviewer 2026-10-10) refuses to delete an account that has an open invoice (a draft, or confirmed and not fully paid), with the plain message "Account has open invoices — settle or void them first". A week later the owner set the rule for every refused delete (2026-10-18, BUG-948): the refusal lists what blocks it, so the user can clear it; the format is the 400 error's `errors` list, one `{type, id}` entry per blocker. BUG-876 predates that rule and carries only the message.
**What happens today:** No refusal at all (BUG-876 is not fixed). Once BUG-876 is fixed as written, the user would get the message without knowing which of the account's invoices are open.
**Example:** "Acme Ltd" has 40 invoices. Two are open: draft INV-118 for 12,500 taka and INV-131, confirmed, 50,000 taka with 20,000 paid. The user presses Delete: the answer should name those two invoices (ids 118, 131) so the screen can link to them, not just say "has open invoices".
**Rules affected:** `delete_account` R5
**Answer:** bug — per the owner's refusal rule (BUG-948 / BUG-1218 format): 400 `app.core.exceptions.ValidationError("Account has open invoices — settle or void them first", errors=blockers)`, `blockers` = one `{"type": "account_invoice", "id": <invoice id>}` per open invoice (account manager R7a), by id ascending, then one `{"type": "other_workspace"}` last, once, if an open invoice of this account carries another workspace's `workspace_id` (HR-16). The manager raises `ValueError(message, blockers)` (follow-up FU-1 for the account manager spec); the service translates. Frontend part (show the blockers in the delete toast / dialog of `AccountsListPage.tsx` and `AccountsLandingPage.tsx`) → BUG-2985 (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-2984 — the open-invoices refusal carries its blockers. Rules: `delete_account` R5; manager part FU-1. BUG-2985 — frontend note, no backend test.

### New questions

### Q1. Which manager refusals the service translates, and to what — ✅ decided
**Background:** The manager signals every refusal with a plain `ValueError` whose text says what is wrong. The application turns `app.core.exceptions.NotFoundError` into 404, `ConflictError` into 409, `ValidationError` into 400 and `BusinessRuleError` into 422; a bare `ValueError` is a 500. The approved manager spec states the intended status of each refusal ("404 at the API", "409 at the API", …) and leaves the translation to this service. Today only `assign_tag` / `unassign_tag` translate (any message containing "not found" → 404, anything else → 422).
**What happens today:** On create / update / delete every `ValueError` is re-raised unchanged (500).
**Example:** Once BUG-874 is fixed, creating "Beta Traders" with code `SUP-001`, already used by "Acme Ltd", would answer 500 instead of 409 "Account code 'SUP-001' already exists".
**Rules affected:** `create_account` R3; `update_account` R3; `delete_account` R3–R5
**Suggested answer:** translate exactly the refusals the manager spec names, after the rollback, keeping the manager's text as the detail unless the manager spec gives another (`Account with ID {id} not found`); any other `ValueError` passes unchanged (a programming error should stay a 500, not become a misleading 4xx — as `machine_item_service` Q1). Alternative: a blanket `ValueError` → 422 as on the tag endpoints.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-21). Part of BUG-2986 / BUG-871 / BUG-874 / BUG-876 / BUG-2987 (no new ID).
**Resolution:** `create_account` R3, `update_account` R3, `delete_account` R3–R5 as written.

### Q2. Creating or updating an account with a deleted tag: which status? — ✅ decided
**Background:** BUG-2987 (account manager P8) makes create / update refuse an inactive tag with `Account tag {id} is not active`, the same text `assign_tag` already uses; the manager spec gives no status for it. `assign_tag` answers that text with 422 today.
**What happens today:** The tag is attached (BUG-2987 not fixed); once fixed, the refusal would be a 500 (Q1).
**Example:** Tag 7 "Old vendor" was deleted. `POST /accounts/` with `tag_ids: [7]` should answer the same as `POST /accounts/5/tags/7/`: 422 "Account tag 7 is not active".
**Rules affected:** `create_account` R3; `update_account` R3
**Suggested answer:** 422 `BusinessRuleError`, same detail, as `assign_tag`. Alternative: 400.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-21). Part of BUG-2987 (no new ID).
**Resolution:** 422 `BusinessRuleError`. Rules: `create_account` R3, `update_account` R3.

### Q3. Deleting an already-deleted account once BUG-862 is fixed — ✅ decided
**Background:** `delete_account` first looks the account up with the manager's `get_account` and answers 404 when it gets nothing. BUG-862 (HR-4) makes `get_account` return nothing for a soft-deleted account by default. BUG-2986 (P1) says a second delete answers 400 "already deleted".
**What happens today:** The pre-check finds the deleted account, the manager refuses with "already deleted", and the user gets 500 (P1). After BUG-862 alone, the pre-check would answer 404 instead, and the manager's "already deleted" would never be reached.
**Example:** Second Delete on "Acme Ltd" from a stale tab: 400 "Account 812 is already deleted" — not "not found", which would suggest the account never existed.
**Rules affected:** `delete_account` R3
**Suggested answer:** 400 `Account {account_id} is already deleted` before and after BUG-862: the pre-check asks for deleted accounts too (`include_deleted=True`), or is dropped and the manager's refusal translated. Alternative: 404, as HR-4 does for reads.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-21), per BUG-2986 / BUG-940 ("already deleted → 400"). Part of BUG-2986 (no new ID).
**Resolution:** 400 before and after BUG-862. Rules: `delete_account` R3.

### Q4. `update_account`'s "manager returned nothing" check can never fire — remove
**Background:** After calling the manager, `update_account` raises 404 `Account with ID {id} not found` when the manager returns nothing, and has a separate `except NotFoundError` that does the same as the general `except`. The manager never returns nothing: it returns the account or raises `ValueError`.
**What happens today:** The check and that `except` branch are never taken (lines 356–357, 365–367). The 404 the endpoint documents is instead a 500 (P1).
**Example:** No request reaches it; once P1 is fixed the 404 comes from the translation of the manager's refusal.
**Rules affected:** none (Not specified)
**Answer:** remove — decided by Claude under the reviewer's delegation (2026-11-21); dead code, as account manager Q11.
**Resolution:** listed in `docs/testing/dead-code-removal-checklist.md` (`app/services/account_service.py:356-357, 365-367`); Not specified.

### Q5. `AccountService.get_account` has no caller — remove
**Background:** `get_account` returns the account or raises 404. Every endpoint uses `get_account_with_tags` instead; nothing in `app/`, `scripts/` or `tests/` calls it.
**What happens today:** Unreachable from any request or job. (Like `get_account_with_tags` it also returns soft-deleted accounts — BUG-862.)
**Example:** A fix of BUG-862 made only in the reachable path would leave this copy behaving the old way for whoever calls it next.
**Rules affected:** none (Not specified)
**Answer:** remove — decided by Claude under the reviewer's delegation (2026-11-21); dead code, as account DAO P3.
**Resolution:** listed in `docs/testing/dead-code-removal-checklist.md` (`app/services/account_service.py:72-94`); Not specified.

**Permission checks:** none. Every endpoint needs a workspace member; the writes need an active user. Any member may create, edit (bank details included) and delete accounts — see Notes for future work in the report, not a rule here.

## Follow-ups for other reviews
> Nothing below is a rule of this service and no bug is logged for it here.

| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **Account manager** (`app/managers/account_manager.py`, `delete_account` R7) | BUG-2984: the open-invoices refusal must carry its blockers — `ValueError("Account has open invoices — settle or void them first", blockers)` with the list described in P2; R7's message stays. | P2 |
| FU-2 | **Accounts endpoint** (`app/api/v1/endpoints/accounts.py`) | BUG-2983 (`ge=1` on `limit` of `/by-tag/`); BUG-140 (read client IP / user agent and pass them); BUG-878 / BUG-862 (expose `include_inactive` on `GET /accounts/`, `include_deleted` on `GET /accounts/{id}/`); `unassign_tag` passes `current_user.id` (BUG-873). | R-rules below |
| FU-3 | **Frontend** (`AccountsListPage.tsx`, `AccountsLandingPage.tsx`) | The delete button and toast say "deactivate" ("Failed to deactivate account"), but the backend soft-deletes: the account leaves every list and there is no restore endpoint. Wording only; noted with BUG-2985. | read while checking P2 |

## Overview
`AccountService` is the transaction boundary of the `/accounts/` endpoints: suppliers, clients and other external parties of a workspace, and their tags. It calls `AccountManager` for every account and tag change, `AccountInvoiceManager.list_accounts_hub_page` for the accounts hub, and two DAO lookups for "accounts with tag N". Besides commit and rollback it (a) turns the manager's `ValueError` refusals into the application's 4xx errors and (b) builds the response dicts — every account with its tag list, and on the hub its open payable / receivable balances. The endpoint re-reads the account with `get_account_with_tags` after create and update.

**Callables:** 11 specified · 4 not specified
**Externals to mock:** none (`utcnow` only through the manager, as in its spec).
**Integration-only behavior:** the HTTP bodies of the translated errors (`tests/unit/core/exceptions.spec.md`); the endpoint's query bounds (BUG-867, BUG-2983) and parameters exposed per FU-2; `has_more` on the hub (computed by the endpoint).

**Facts for the test designer**
- Import: `from app.services.account_service import AccountService, account_service`. `AccountService()` takes no arguments; the manager is the attribute `account_manager` (the singleton of `app.managers.account_manager`). `account_invoice_manager`, `account_dao`, `account_tag_dao` are module globals of `app.services.account_service` (patch them there).
- Errors are `app.core.exceptions`: `NotFoundError` (`.status_code` 404, `.error_type` `not_found`), `ConflictError` (409, `conflict`), `ValidationError` (400, `validation_error`, `.errors`), `BusinessRuleError` (422, `business_rule_violation`); all have `.detail`.
- **Account dict** (built by `_account_dict_with_tags`; the three other builders produce the same keys): `id`, `workspace_id`, `name`, `account_code`, `primary_contact_person`, `primary_email`, `primary_phone`, `secondary_contact_person`, `secondary_email`, `secondary_phone`, `address`, `city`, `country`, `postal_code`, `payment_preferences`, `bank_details`, `allow_invoices`, `is_active`, `created_at`, `account_tags` — exactly these 20 keys, values as stored. `account_tags` is a list of dicts with exactly `id`, `name`, `tag_code`, `color`, `icon`, `is_system_tag`, one per tag of `AccountManager.get_tags_for_account`, in its order.
- Rows: build accounts and tags as the account manager spec's Facts say (`AccountTag` model fills its defaults; invoices inserted directly in a consistent state from that spec's table).
  - **Account** — `app.models.account.Account`, table `accounts`. Only `workspace_id` (FK `workspaces.id`) and `name` (≤ 255) are NOT NULL without a default. Python defaults: `allow_invoices True`, `is_active True`, `is_deleted False`; `created_at` is `server_default now()`; `updated_at` `onupdate now()`. Everything else is nullable with no default (`account_code` ≤ 50, the contact, address, `payment_preferences`, `bank_details` columns, `created_by` / `updated_by` / `deleted_by` → `profiles.id`, `deleted_at`). So `Account(workspace_id=…, name=…)` is a valid row; `created_by` is optional. (G1)
  - **Tag assignment** — `app.models.account_tag_assignment.AccountTagAssignment`, table `account_tag_assignments`. NOT NULL: `workspace_id`, `account_id` (FK `accounts.id`, cascade), `tag_id` (FK `account_tags.id`, cascade); `assigned_at` NOT NULL with Python default `utcnow`; `assigned_by` (→ `profiles.id`) nullable. Unique constraint `uq_account_tag` on `(account_id, tag_id)`. (G1)
  - **Bugs of the tag list are open today** (G3): BUG-865 (deleted tags listed) and BUG-1486 (no order) are both `open`, and `get_tags_for_account` filters only on the assignment's workspace and account. A card asserting "a deleted tag is not listed" or "tags in the R5 order" is strict xfail with that bug; a card with only live tags in a single-tag account passes today.

**Notes for the test designer**
- Session, commits, TC4 / TC5 patching: as `base_service.spec.md` Notes. Patch `account_service.account_manager.<method>` to raise a given `ValueError` to test a translation independently of whether the manager's fix exists yet; add one end-to-end case per bug through the real manager (strict xfail until the manager fix).
- BUG-873, BUG-140 add parameters: today passing them raises `TypeError` → strict xfail.

## Not specified
- `AccountService.__init__` — stores the manager, no logic.
- `account_service` — module-level singleton.
- `AccountService.get_account` — dead code, to be removed (reviewer delegation, Q5).
- `update_account`: the "manager returned nothing" check and its `except NotFoundError` (lines 356–357, 365–367) — dead code, to be removed (reviewer delegation, Q4).

---

## `AccountService.create_account(db, account_in, workspace_id, user_id, ip_address=None, user_agent=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /accounts/`)

**Inputs:** `account_in` `AccountCreate` (account manager spec); `ip_address`, `user_agent` — [BUG-140] new, passed to the manager.

**Returns:** the new `Account`, committed and re-read.

**Rules:**
- **R1.** The account is created as the manager's `create_account` creates it (its R1–R12, with its bugs), and the whole result — account, tag assignments, usage counts, audit row — is committed (TC1). The returned row is re-read (TC2: `created_at` loaded).
- **R2.** Any exception rolls everything back (TC3, TC4); after the commit, a failing re-read leaves the account saved (TC5).
- **R3.** [BUG-871 / BUG-874 / BUG-2987] (Q1, Q2) The manager's refusals reach the caller translated, after the rollback, nothing saved: `Account tag {id} not found` → `NotFoundError` 404, same detail; `Account code '{code}' already exists` → `ConflictError` 409, same detail; `Account tag {id} is not active` → `BusinessRuleError` 422, same detail. Any other `ValueError` reaches the caller unchanged. *(Today: no translation; and the manager raises none of them yet — unknown tags are skipped, verified.)*
- **R4.** [BUG-140] The client IP and user agent passed in reach the audit row (account manager `create_account` R10). *(Today: no such parameters.)*

**Errors:** as R3; `pydantic.ValidationError` is the schema's, before the call.

**Side effects:** the manager's writes, committed.

---

## `AccountService.get_account_with_tags(db, account_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /accounts/{id}/`; as the account's existence check of `GET /accounts/{id}/invoice-summary/`, `/open-invoices/`, `/invoices/`; and as the response of create, update, `assign_tag`)

**Inputs:** `include_deleted` — [BUG-862] new, default `False`, passed to the manager's `get_account`.

**Returns:** the account dict (Facts) with its tags.

**Rules:**
- **R1.** A live account of the workspace → its dict; inactive (not deleted) accounts too.
- **R2.** No account with that id, or one of another workspace → `NotFoundError` 404 `Account with ID {account_id} not found`.
- **R3.** [BUG-862] (HR-4) A soft-deleted account → the same 404 by default; with `include_deleted=True` its dict is returned. Through this, the three invoice endpoints that use this call as an existence check answer 404 for a deleted account. *(Today: returned, 200 — verified.)*
- **R4.** `account_tags` follows `AccountManager.get_tags_for_account` (its R1–R5: BUG-865 only active tags, BUG-1486 order). Both bugs are open today (Facts, G3): "deleted tag not listed" and "ordered" cards are strict xfail with BUG-865 / BUG-1486.
- **R5.** Read only (TC6).

**Errors:** `NotFoundError` 404 `Account with ID {account_id} not found`.

**Side effects:** none

---

## `AccountService.get_accounts_with_tags(db, workspace_id, search=None, tag_code=None, skip=0, limit=100, include_inactive=False)`
**Shape:** search · **Persistence:** reads · **Visibility:** public (used by: `GET /accounts/`)

**Inputs:** `include_inactive` — [BUG-878] new, default `False`, passed to the manager.

**Rules:**
- **R1.** The accounts are the manager's `search_accounts` for `name = search`, `tag_code`, `skip`, `limit` (its R1–R14 with their bugs: filters, order BUG-866, paging), in that order; each becomes the account dict with its tags (Facts; tags as `get_tags_for_account`). No match → `[]`.
- **R2.** [BUG-878] `include_inactive=True` is passed on (manager R1a). *(Today: no such parameter.)*
- **R3.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none

---

## `AccountService._account_dict_with_tags(db, account, workspace_id)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal (used by: `get_accounts_hub_page`)

**Rules:**
- **R1.** Returns the account dict of Facts for `account`, its tags read for `workspace_id` with `get_tags_for_account`. `account` is not re-checked (state, workspace).

---

## `AccountService._rollup_from_subquery_row(row)` (static)
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `get_accounts_hub_page`)

**Rules:**
- **R1.** `row` `None` → `(Decimal(0), 0, False)`. (Not reached from the hub today: the DAO always gives an object; testable by direct call.)
- **R2.** Otherwise `(Decimal(row.outstanding_total), int(row.open_count), bool(row.has_overdue))`; a missing attribute, `None` or `0` gives `Decimal(0)` / `0` / `False`. A Decimal value keeps its scale (`Decimal("1500.00")` stays `1500.00`); the zero is `Decimal("0")`, not `0.00`. No rounding.

---

## `AccountService.get_accounts_hub_page(db, *, workspace_id, section="overview", search=None, skip=0, limit=50)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /accounts/hub/`, `section` ∈ overview / payable / receivable, `1 ≤ limit ≤ 500`)

**Returns:** `(items, total)`.

**Rules:**
- **R1.** Rows and `total` are `AccountInvoiceManager.list_accounts_hub_page` for the same arguments (its R1–R7: which accounts — BUG-636; what counts as open — confirmed only, BUG-634; overdue — BUG-635; search — BUG-622; order — BUG-623; `total` before paging). Items keep the manager's order; `total` is returned unchanged.
- **R2.** Each item is the account dict (`_account_dict_with_tags`) plus `open_balance` = `{"payable_outstanding", "receivable_outstanding", "open_payable_count", "open_receivable_count", "has_overdue_payable", "has_overdue_receivable"}` from the payable and receivable rollups (`_rollup_from_subquery_row`). An account with no open invoice of a type gets `Decimal("0")`, `0`, `False` for it (verified).
- **R3.** Read only (TC6).

**Errors:** none of its own. **Side effects:** none

---

## `AccountService.update_account(db, account_id, account_in, workspace_id, user_id, ip_address=None, user_agent=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /accounts/{id}/`)

**Inputs:** `account_in` `AccountUpdate`; `ip_address`, `user_agent` — [BUG-140] new.

**Returns:** the `Account`, committed and re-read.

**Rules:**
- **R1.** The account is changed as the manager's `update_account` changes it (its R1–R20b, with its bugs), committed (TC1), re-read (TC2: `updated_at` loaded when the row changed).
- **R2.** Any exception rolls everything back (TC3, TC4); TC5 as `create_account`.
- **R3.** [BUG-2986 / BUG-871 / BUG-874 / BUG-2987] (P1, Q1, Q2) The manager's refusals reach the caller translated, after the rollback, nothing saved: `Account {id} not found` (missing, other workspace — BUG-440, soft-deleted — BUG-863) → `NotFoundError` 404 `Account with ID {account_id} not found`; tag not found → 404, duplicate code → 409, inactive tag → 422, each with the manager's text, as `create_account` R3. Any other `ValueError` reaches the caller unchanged. *(Today: every one is a bare `ValueError` (500) — verified for a missing id and another workspace's account, whose text today also names the workspace: `Account N does not belong to workspace W`.)*
- **R4.** [BUG-140] IP / user agent reach the audit row (manager R18). *(Today: no such parameters.)*

**Errors:** as R3.

**Side effects:** the manager's writes, committed.

---

## `AccountService.get_accounts_by_tag_id(db, tag_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /accounts/by-tag/{tag_id}/`, `limit ≤ 100`)

**Rules:**
- **R1.** A tag that does not exist, or belongs to another workspace → `NotFoundError` 404 `Account tag {tag_id} not found` (verified).
- **R2.** [BUG-2982] (HR-4) A deleted tag (`is_active = False`) → the same 404 `Account tag {tag_id} not found`; nothing is listed. *(Today: found; the tag's accounts are listed, 200 — verified; after BUG-1481 alone it would be `[]`, 200.)*
- **R3.** Otherwise the accounts are `AccountDAO.get_accounts_by_tag_id` for `tag_id`, `skip`, `limit` (its R1–R5: live and active accounts only, assignments of the workspace, order BUG-1480, paging), each as the account dict with its tags (Facts; tags as `get_tags_for_account`, BUG-865 / BUG-1486). No account → `[]`.
- **R4.** Read only (TC6).
- **R5.** [BUG-2983] (HR-7) `limit` must be at least 1 — 422 at the endpoint (integration-only). *(Today: `limit=0` → `[]` (verified); a negative `limit` → `DataError` from Postgres.)*

**Errors:** `NotFoundError` 404 `Account tag {tag_id} not found`.

**Side effects:** none

---

## `AccountService.assign_tag(db, account_id, tag_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `POST /accounts/{id}/tags/{tag_id}/`)

**Returns:** the account dict with tags (as `get_account_with_tags`), read after the commit.

**Rules:**
- **R1.** The tag is attached as the manager's `assign_tag` does it (its R1–R10 with its bugs; already assigned → no change), committed (TC1); the returned dict lists the tag.
- **R2.** A `ValueError` from the manager is rolled back and translated: a message containing `not found` → `NotFoundError` 404 with the manager's text as detail (`Account {account_id} not found` — missing, other workspace, and per BUG-863 soft-deleted; `Account tag {tag_id} not found`); any other message → `BusinessRuleError` 422 with the manager's text (`Account tag {tag_id} is not active`). Nothing is saved (verified). The match is on the lower-case text `not found`, case-sensitive.
- **R3.** Any other exception from the manager or the commit: rollback, re-raised unchanged (TC3, TC4).
- **R4.** If reading the dict after the commit raises, that exception reaches the caller and the assignment stays saved (TC5).
  - The read is the service's own `get_account_with_tags` (`self.get_account_with_tags(db, account_id, workspace_id=…)`), called inside the same `try`. Patch point: `patch.object(service, "get_account_with_tags", side_effect=RuntimeError("boom"))` on the instance under test (or `AccountService.get_account_with_tags`). (G2)
  - **R4a.** Because the read sits inside the `try`, its exception goes through the same `except` clauses: a `RuntimeError` (or any non-`ValueError`, including the read's own `NotFoundError`) reaches the caller unchanged; a `ValueError` raised by the read is translated as R2 (`not found` in the text → `NotFoundError` 404, else `BusinessRuleError` 422). In every case the rollback after the commit undoes nothing: the assignment row, `usage_count` change and audit row stay saved. (G2)

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| account missing / other workspace / (BUG-863) soft-deleted | `NotFoundError` 404 | `Account {account_id} not found` |
| tag missing / other workspace | `NotFoundError` 404 | `Account tag {tag_id} not found` |
| tag inactive | `BusinessRuleError` 422 | `Account tag {tag_id} is not active` |

**Side effects:** the manager's writes, committed.

---

## `AccountService.unassign_tag(db, account_id, tag_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `DELETE /accounts/{id}/tags/{tag_id}/`)

**Inputs:** `user_id` — [BUG-873] new, required, passed to the manager's `unassign_tag` (its Inputs). *(Today: no such parameter; the endpoint has the user but does not pass it.)*

**Returns:** `None`.

**Rules:**
- **R1.** The tag is removed as the manager's `unassign_tag` does it (its R1–R7), committed (TC1).
- **R2.** `ValueError` translation as `assign_tag` R2, after the rollback, nothing saved. With BUG-879, "tag not assigned" (also an unknown tag id) → 404 `Tag {tag_id} assignment not found for account {account_id}`. *(Today: 422 `Tag {tag_id} is not assigned to account {account_id}` — verified.)*
- **R3.** Other exceptions: rollback, unchanged (TC3, TC4).
- **R4.** [BUG-873] `user_id` reaches the manager, which stamps it on the audit row and `updated_by` (manager R7). *(Today: `TypeError` when passed.)*

**Errors:** `NotFoundError` 404 (account missing / other workspace / soft-deleted; tag not assigned, with BUG-879).

**Side effects:** the manager's writes, committed.

---

## `AccountService.delete_account(db, account_id, workspace_id, user_id, ip_address=None, user_agent=None)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /accounts/{id}/`)

**Inputs:** `ip_address`, `user_agent` — [BUG-140] new.

**Returns:** `None`.

**Rules:**
- **R1.** A live account of the workspace (active or not) is soft-deleted as the manager's `delete_account` does it (its R4–R6, R8, R10), committed (TC1).
- **R2.** No account with that id, or one of another workspace → `NotFoundError` 404 `Account with ID {account_id} not found`, nothing written (verified).
- **R3.** [BUG-2986] (P1, Q3) An already-deleted account → `ValidationError` 400 `Account {account_id} is already deleted`, nothing written — also once BUG-862 hides deleted accounts from the manager's default `get_account`. *(Today: bare `ValueError`, 500 — verified.)*
- **R4.** [BUG-876] An account with an open invoice (manager R7, R7a–R7c) is refused with 400, nothing written (rollback). *(Today: deleted — the manager does not check.)*
- **R5.** [BUG-2984] (P2) The 400 of R4 is `app.core.exceptions.ValidationError` with detail `Account has open invoices — settle or void them first` (em dash, U+2014) and `errors` = the blockers: one `{"type": "account_invoice", "id": <invoice id>}` per open invoice of the account, by id ascending, then one `{"type": "other_workspace"}` last, once, when any open invoice of the account carries another workspace's `workspace_id` (HR-16: no id of it). *(Today: no refusal; and BUG-876 as written carries no list. Requires the manager to raise `ValueError(message, blockers)` — FU-1.)*
- **R5a.** [BUG-2984] An open invoice (account manager R7a: `account_id` = this account, whatever its `workspace_id`) that carries **another** workspace's `workspace_id` counts as open on its own (HR-16: invalid data, never a normal state). It blocks the delete but never appears as an `account_invoice` entry: the `account_invoice` entries list only open invoices of the caller's workspace, and all foreign ones together give the single trailing `{"type": "other_workspace"}`. So an account whose only open invoice is foreign is refused with 400 and `errors == [{"type": "other_workspace"}]`; one own open invoice 7 plus two foreign ones gives `[{"type": "account_invoice", "id": 7}, {"type": "other_workspace"}]`. A foreign invoice that is voided or fully paid blocks nothing. (G4; decided by Claude under the reviewer's delegation (2026-11-21), following HR-16 and manager R7a)
- **R6.** Any other exception: rollback, re-raised unchanged (TC3, TC4).
- **R7.** [BUG-140] IP / user agent reach the audit row (manager R10). *(Today: no such parameters.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `NotFoundError` 404 | `Account with ID {account_id} not found` |
| already deleted (BUG-2986) | `ValidationError` 400 | `Account {account_id} is already deleted` |
| open invoices (BUG-876, BUG-2984) | `ValidationError` 400, `errors` = blockers | `Account has open invoices — settle or void them first` |

**Side effects:** the manager's writes, committed; none when refused.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 53–66 | manager create, commit, refresh | `create_account` R1 |
| 68–70 | any exception → rollback, re-raise (no translation today) | `create_account` R2, R3 |
| 92–95 | `get_account` — no caller | Not specified (Q5) |
| 117–119 | manager returns `None` → 404 / account (deleted too, today) | `get_account_with_tags` R1–R3 |
| 121–158 | tags read, dict built, loop over 0 / many tags | `get_account_with_tags` R4; Facts |
| 182–189 | manager search with `search` as `name` | `get_accounts_with_tags` R1, R2 |
| 193–234 | loop over 0 / many accounts | `get_accounts_with_tags` R1 |
| 239–273 | dict with tags | `_account_dict_with_tags` R1 |
| 277–278 | `row is None` | `_rollup_from_subquery_row` R1 |
| 279–282 | `or 0` / `getattr` defaults / `bool` | `_rollup_from_subquery_row` R2 |
| 294–320 | manager hub page; loop over rows; `open_balance` | `get_accounts_hub_page` R1, R2 |
| 348–354, 360–363 | manager update, commit, refresh | `update_account` R1 |
| 356–357, 365–367 | manager returned nothing; `except NotFoundError` | Not specified (Q4) |
| 368–370 | any exception → rollback, re-raise | `update_account` R2, R3 |
| 386–388 | tag not in workspace → 404 (inactive tag passes today) | `get_accounts_by_tag_id` R1, R2 |
| 390–392 | DAO page | `get_accounts_by_tag_id` R3, R5 |
| 395–431 | loop over 0 / many accounts | `get_accounts_by_tag_id` R3 |
| 443–451 | manager assign, commit, re-read dict | `assign_tag` R1, R4 |
| 452–456 | `ValueError` with `not found` → 404 | `assign_tag` R2 |
| 457 | other `ValueError` → 422 | `assign_tag` R2 |
| 458–460 | other exception → rollback, re-raise | `assign_tag` R3 |
| 471–477 | manager unassign (no `user_id`), commit | `unassign_tag` R1, R4 |
| 478–483 | `ValueError` → 404 / 422 | `unassign_tag` R2 |
| 484–486 | other exception | `unassign_tag` R3 |
| 509–511 | pre-check `get_account` → `None` → 404 (deleted found today) | `delete_account` R2, R3 |
| 514–522 | manager delete, commit | `delete_account` R1, R4, R5 |
| 524–529 | `NotFoundError` / any exception → rollback, re-raise | `delete_account` R2, R3, R6 |
| `dao/account_invoice.py` 299–306 | hub agg: `None` → 0 / False | `get_accounts_hub_page` R2 |
| `dao/base.py` 169–194 | tag by id and workspace, raw (inactive returned) | `get_accounts_by_tag_id` R1, R2 |

## Gap log
- G1 (`account_service.cases.md` gap 1) — Fact — Facts "Rows" now name the `Account` and `AccountTagAssignment` models, tables, NOT NULL columns, defaults and the `uq_account_tag` constraint. The cards' assumption holds: `workspace_id` + `name` suffice, `created_by` is optional; assignment needs `workspace_id`, `account_id`, `tag_id`, with `assigned_at` defaulted and `assigned_by` optional.
- G2 (gap 2) — Fact — `assign_tag` R4 names the read (`self.get_account_with_tags`, inside the `try`) and its patch point; new R4a: a non-`ValueError` from the read reaches the caller unchanged, a `ValueError` is translated as R2, and the assignment stays saved either way.
- G3 (gap 3) — Fact — BUG-865 and BUG-1486 are both open today (the DAO filters only on the assignment's workspace and account); Facts and `get_account_with_tags` R4 say such cards are strict xfail with those IDs.
- G4 (gap 4) — Contradiction resolved / Intent (delegated) — new `delete_account` R5a: a foreign-workspace open invoice blocks on its own and shows only as the one `other_workspace` entry; the reading of ASV-D-20 and D-23 is confirmed. Same bug BUG-2984, no new ID.
- G5 (2026-11-22, routed by the `account_service` verifier; decided under the reviewer's delegation) — Contradiction (wrong bug IDs) — the rules cited BUG-124 (attachment allowlist row) and BUG-629 (invoice account-change row), cited by pattern from the account manager spec. Opened BUG-2986 (account refusals answer 500 instead of 4xx; pattern `wrong-error-type-uncaught`, as BUG-124) and BUG-2987 (create / update accept an inactive tag that `assign_tag` refuses; pattern `inconsistent-sibling-validation`, as BUG-629), and re-tagged every rule. Behaviour unchanged. `account_manager.spec.md` re-tagged the same way.
