# Spec — `app/dao/account.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1–P3 decided by Claude under the reviewer's delegation (2026-11-03). None of them is the owner's own answer. The house-rule lines stand. Every decision the approved account manager spec (`tests/unit/managers/account_manager.spec.md`) already made about this DAO's search is reused with its bug ID; nothing here contradicts it.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Soft-deleted rows are kept but do not show up (owner, 2026-10-10); things of a soft-deleted parent are hidden by the parent's state, their own rows untouched. For account tags "deleted" is `is_active = False` (account manager spec, Facts). Raw lookups stay raw (HR-4 scope). Refusals list their blockers. HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `schema.py`, `v_acct.py`, `v_acct2.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, defaults, constraints, indexes and the tables that reference it; `get_accounts_in_workspace` with live, inactive, soft-deleted, soft-deleted-but-active and other-workspace accounts; name `"acme"`, `""`, `"%"`, `"_"`, `"   "`, `" acme "`; tag code `supplier`, `Supplier`, `"supplier "`, `""`, an inactive tag's code, two tags of one code on one account (one row back), a link recorded under the other workspace, a link to another workspace's tag; name + tag together; `limit=0`, `skip`, negative `limit` / `skip` (`DataError` 2201W / 2201X); 107 live accounts (100 back); the SQL (`SELECT DISTINCT … LIMIT … OFFSET`, no `ORDER BY`); the query plan (Unique over a Sort that starts with `id`); that `SELECT DISTINCT` with `ORDER BY lower(name)` is refused by Postgres (42P10); `count_active_accounts` for both workspaces and an unknown one; `get_accounts_by_tag_id` with an active tag, an inactive tag, an inactive and a deleted account, another workspace's tag, an unknown tag, the other workspace; order under a forced sequential scan before and after an update. **Read, not run:** `AccountManager.search_accounts`, `AccountService.get_accounts_by_tag_id`, `AccountInvoiceManager.get_invoices_hub_summary`, the other callers of the inherited lookups. **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A search of only spaces finds almost nothing, and `" acme "` does not find "Acme Ltd" | bug — the search text is trimmed; blank means no name filter (BUG-637, as in the account manager spec) | Claude, delegated |
| P2 | Deactivated accounts can never be listed | bug — new `include_inactive` option (BUG-878, as in the account manager spec) | Claude, delegated |
| P3 | "Search accounts by name" has no caller anywhere | remove | Claude, delegated |

Decided by house rules: no sort order on both lists (BUG-866 existing, BUG-1480 new); `%` and `_` in the search act as wildcards (BUG-868 existing); the tag code is compared exactly (BUG-861 existing); a deleted tag still filters (BUG-864 existing) — also in "accounts with tag N" (BUG-1481 new).

### House-rule violations — applied automatically

- **HR-6** `get_accounts_in_workspace` R8 — no sort order. Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-866 (existing; its Module cell already names this file). Note for the fix: the query is `SELECT DISTINCT`, and Postgres refuses `ORDER BY lower(name)` with `SELECT DISTINCT` (verified, 42P10 "for SELECT DISTINCT, ORDER BY expressions must appear in select list"); replacing the tag join + `DISTINCT` by an `EXISTS` sub-query avoids it. Rules: `get_accounts_in_workspace` R8.
- **HR-8** `get_accounts_in_workspace` R3 — the name is placed in `ILIKE '%…%'` unescaped (verified: `%` and `_` alone return every account).
**Answer:** bug — per HR-8 (house rule)
**Resolution:** BUG-868 (existing). Rules: `get_accounts_in_workspace` R3.
- **HR-3** `get_accounts_in_workspace` R5 — the tag code is an exact, case-sensitive match (`Supplier`, `"supplier "` find nothing).
**Answer:** bug — per HR-3 (house rule)
**Resolution:** BUG-861 (existing). Rules: `get_accounts_in_workspace` R5.
- **HR-4** `get_accounts_in_workspace` R6 — an assignment to a deleted (inactive) tag makes the account match.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** BUG-864 (existing). Rules: `get_accounts_in_workspace` R6.
- **HR-6** `get_accounts_by_tag_id` R4 — no sort order on `GET /accounts/by-tag/{tag_id}/`, which pages. Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit` (same order as BUG-866).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1480 (pattern `unordered-pagination`; fix in this file). Rules: `get_accounts_by_tag_id` R4.
- **HR-4** `get_accounts_by_tag_id` R3 — the tag's state is not looked at: "accounts with tag 7" lists the accounts of deleted tag 7 (verified). HR-4: "a deleted tag neither filters nor matches"; BUG-864 is the same gap in the other list.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1481 (pattern `join-ignores-soft-deleted`, per BUG-864; fix in this file). What the endpoint answers for a deleted tag is the account service's (FU-1 (a)). Rules: `get_accounts_by_tag_id` R3.
- **HR-6** inherited `get_by_workspace`, `get_multi` — no order; BUG-100 (existing, fix in `app/dao/base.py` reaches this DAO). No caller on this DAO.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-100 (existing). Rules: inherited R4.

Checked and **not** a new line here: **HR-5** — every filter is in the query, before `LIMIT`; the fixes must stay there. **HR-7** — `GET /accounts/` has no lower bound on `limit` (BUG-867, endpoint); `GET /accounts/by-tag/{tag_id}/` has `le=100` and no lower bound either (FU-1 (b)). **HR-16** — every method filters on the account's own `workspace_id`, and the tag filters on the assignment's `workspace_id`; a link to another workspace's tag is matched (R7) but no writer of the API creates one (`AccountManager` looks the tag up in the caller's workspace). **HR-1, HR-2** — no name is written here (BUG-860, BUG-874 belong to the manager). **HR-9, HR-10** — nothing written.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. A search of only spaces finds almost nothing — 🐞 BUG-637 (existing)
**Background:** `GET /accounts/?search=…` passes the text straight to this method. The account manager spec ruled this a bug (P6) under BUG-637.
**What happens today:** `"   "` matches only names containing three spaces in a row; `" acme "` does not find "Acme Ltd". (Verified.)
**Example:** A user types a space in the search box: the list empties although 40 accounts exist.
**Rules affected:** `get_accounts_in_workspace` R2
**Answer:** bug — per BUG-637 precedent (account manager P6): the text is trimmed; empty after trimming means no name filter. The fix is in this file (the manager passes the text through).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): BUG-637 (existing), no new ID. Rules: `get_accounts_in_workspace` R2 (tagged).

### P2. Deactivated accounts can never be listed — 🐞 BUG-878 (existing)
**Background:** The account manager spec ruled (Q9) that `search_accounts` gains `include_inactive`; this method is its query.
**What happens today:** Only `is_active = True` accounts are returned; there is no option.
**Example:** "Acme Ltd" is switched to inactive and cannot be found again to reactivate it.
**Rules affected:** `get_accounts_in_workspace` R1a
**Answer:** bug — per BUG-878: new parameter `include_inactive` (default `False`, today's behavior); `True` also returns inactive, not-deleted accounts.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): BUG-878 (existing), no new ID. Rules: `get_accounts_in_workspace` R1a (tagged).

### P3. "Search accounts by name" has no caller — 🗑️ remove
**Background:** `search_by_name_in_workspace` is a second name search (active, not deleted, `ILIKE`, no order). Nothing in `app/`, `scripts/` or `tests/` calls it; `GET /accounts/` uses `get_accounts_in_workspace`. Unused DAO methods were ruled `remove` before (item DAO Q4, machine item DAO P7).
**What happens today:** It cannot be reached by any request or job.
**Example:** A fix for BUG-868 made only in `get_accounts_in_workspace` would leave this copy with the old wildcard behavior for whoever calls it next.
**Rules affected:** none (Not specified)
**Answer:** remove — dead code.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/account.py:15`). Not a bug — no BUG ID.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Account service / endpoint** (`app/services/account_service.py`, `app/api/v1/endpoints/accounts.py`) | (a) `get_accounts_by_tag_id` finds the tag with the raw `get_by_id_and_workspace`: a deleted tag passes and, after BUG-1481, gives `[]`; by HR-4 (get by id: deleted → 404) it should answer 404 `Account tag {tag_id} not found`. (b) `GET /accounts/by-tag/{tag_id}/` declares `limit` with `le=100` and no lower bound (HR-7, BUG-867 precedent). (c) Each returned account then reads its tags one by one (`get_tags_for_account` per account): inherits BUG-865 / BUG-1486. | BUG-1481, HR-7 check |
| FU-3 | **Any future hard delete of accounts** | The ORM nulls child foreign keys before the database cascade / RESTRICT acts (inherited R5): add `passive_deletes=True` to `Account.tag_assignments` (and `AccountInvoice`'s `account` backref) so the database decides, and answer a refusal with the blockers (standing decision: refusals list blockers). | inherited R5, G1 |
| FU-2 | **Work order manager** (`app/managers/work_order_manager.py:263`, `:426`) | Takes an account with the raw `get_by_id_and_workspace` and checks only that it exists: a soft-deleted account can be set on a work order (the invoice manager refuses it: "Cannot create invoice for deleted account"). | inherited R3 |

## Overview
`AccountDAO` reads `accounts`, the external parties of a workspace (suppliers, clients, …; what an account is comes from its tags). Callers: `AccountManager` (`search_accounts` ← `GET /accounts/`; and the inherited `get`, `create`, `update`), `AccountService.get_accounts_by_tag_id` ← `GET /accounts/by-tag/{tag_id}/`, `AccountInvoiceManager.get_invoices_hub_summary` (the "active accounts" KPI), and the inherited `get_by_id_and_workspace` in the invoice, purchase order, work order and sales code. It protects workspace isolation and keeps deleted and inactive accounts out of lists and counts. It validates nothing, writes nothing of its own and never commits.

**Callables:** 3 specified (+ 1 section on inherited behavior) · 2 not specified
**Externals to mock:** none. `created_at` and `updated_at` come from the database clock.
**Integration-only behavior:** none.

**Model facts (table `accounts`, class `app.models.account.Account`):** `id` PK; `workspace_id` NOT NULL → `workspaces` ON DELETE CASCADE; `name` varchar(255) NOT NULL, plain index, **not unique**; `account_code` varchar(50); contacts, emails (varchar 255), phones (varchar 50), `address`, `city` / `country` (100), `postal_code` (20), `payment_preferences`, `bank_details`; `allow_invoices`, `is_active` (Python default `True`), `is_deleted` (Python default `False`) NOT NULL with no database default; `created_at` NOT NULL `DEFAULT now()`; `updated_at` set by `onupdate=now()`; `created_by`, `updated_by`, `deleted_by` → `profiles`; `deleted_at`. Indexes: primary key, `ix_accounts_id`, `ix_accounts_name`, `ix_accounts_workspace_id`; no unique or check constraint, no trigger. Referenced (`ON DELETE RESTRICT`) by invoices, purchase / sales / expense / work orders and their templates; `account_tag_assignments` cascade.
- Account soft delete = `is_deleted = True` (the manager also sets `is_active = False`); a row with `is_deleted = True, is_active = True` is possible (BUG-863) and is treated as deleted by every method here.
- `account_tags.tag_code` has no unique index: two tags of one workspace can share a code. `account_tag_assignments` is unique on `(account_id, tag_id)` (`uq_account_tag`), across workspaces.
- Test database collation `English_United States.1252`.

**Notes for the test designer:**
- Use the singleton `account_dao`. Every parameter after `db` is keyword-only.
- Build rows directly: `Account(workspace_id, name, …)`, `AccountTag(workspace_id, name, tag_code, is_active=…)`, `AccountTagAssignment(workspace_id, account_id, tag_id)`; `make_workspace` from `tests/unit/factories.py`. The session has `autoflush=False`: flush before calling.
- **Order (BUG-866, BUG-1480):** today's order follows the plan; on the test database the `DISTINCT` was a Unique over a Sort starting with `id`, so rows came back `id` ascending, and the account manager spec recorded a hash order. Neither is promised. Use names whose intended order differs from both `id` ascending and descending (e.g. inserted "Zulu", "apple", "Banana", "mango", "Kilo", "delta"), mark the case **non-strict** xfail, never weaken the assertion. Every other case compares **sets** of ids.
- **Not tagged cases that hold today** are plain passes; tagged rules whose today's result is deterministic (BUG-637, BUG-861, BUG-864, BUG-868, BUG-878, BUG-1481) are **strict** xfail.
- **Database errors:** wrap in `with db.begin_nested():` inside `pytest.raises(...)`.

## Not specified
- `account_dao` — module-level singleton, no logic.
- `AccountDAO.search_by_name_in_workspace` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-03); P3).
- Inherited `BaseDAO` methods — base spec; only what is specific to `Account` is stated below.

---

## `AccountDAO.get_accounts_in_workspace(db, *, workspace_id, name=None, tag_code=None, skip=0, limit=100)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `AccountManager.search_accounts` ← `GET /accounts/`, with the caller's `name`, `tag_code`, `skip`, `limit`)

**Purpose:** One page of the workspace's accounts, optionally narrowed by name text and tag code.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the account's `workspace_id` |
| `name` | str or None | falsy → no name filter |
| `tag_code` | str or None | falsy → no tag filter |
| `skip`, `limit` | int, `0` / `100` | not validated |
| `include_inactive` | bool, default `False` | *(requires new parameter — BUG-878)* |

**Returns:** a `list` of `Account` (possibly empty), each account at most once.

**Rules:**
- **R1.** Only accounts of `workspace_id` with `is_active = True` and `is_deleted = False` are returned. Inactive accounts, soft-deleted accounts (also one still marked active) and accounts of other workspaces never appear.
- **R1a.** [BUG-878] (P2) With `include_inactive=True`, inactive, not-deleted accounts of the workspace are returned too; deleted ones and other workspaces' never. Default `False` is today's R1. *(Today: no such parameter — passing it raises `TypeError`.)*
- **R2.** [BUG-637] (P1) `name` is trimmed; `None`, `""` or whitespace-only means no name filter (`"   "` returns every account of R1); `" acme "` matches "Acme Ltd". *(Today: `None` and `""` mean no filter, but `"   "` returns only names containing three spaces in a row and `" acme "` matches nothing.)*
- **R3.** A non-blank `name` keeps accounts whose name contains it, case-insensitively, anywhere. [BUG-868] (HR-8) `%`, `_` and `\` match themselves: `"50%"` finds "50% off" and not "500 Ltd"; `"%"` alone finds only names containing `%`. *(Today: `%` and `_` are wildcards — `"%"` and `"_"` each return every account; `\` escapes the next character.)*
- **R4.** `tag_code` `None` or `""` → no tag filter.
- **R5.** A `tag_code` keeps accounts with at least one assignment recorded in `workspace_id` (the assignment's own `workspace_id`) to a tag with that code. [BUG-861] (HR-3) The code is compared trimmed and case-insensitively: `Supplier` and `"supplier "` match code `supplier`. *(Today: exact, case-sensitive — both find nothing.)* An assignment recorded under another workspace never counts, even for this workspace's account.
- **R6.** [BUG-864] (HR-4) Only active tags count: an account whose only tag with that code is inactive is not returned; with an active and an inactive tag of the same code, the active one decides. *(Today: inactive tags match.)*
- **R7.** An account matching through several assignments (two tags of one code) is returned once. The tag's own `workspace_id` is not compared: a link recorded in this workspace to another workspace's tag with that code matches (HR-16 invalid data; the API never writes it).
- **R8.** [BUG-866] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`: "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu". *(Today: no `ORDER BY`; plan-dependent, see Notes.)*
- **R9.** `name` and `tag_code` together: both must hold.
- **R10.** `skip` / `limit` are applied after every filter (and R8): defaults 0 and 100 — of 107 matching accounts, 100 are returned; `limit=0` or `skip` past the end returns `[]`. A negative `limit` / `skip` raises `DataError` (2201W / 2201X).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, pgcode `2201W` | `LIMIT must not be negative` |
| negative `skip` | `DataError`, pgcode `2201X` | `OFFSET must not be negative` |

**Side effects:** none

---

## `AccountDAO.count_active_accounts(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceManager.get_invoices_hub_summary` ← the invoices hub, "total active accounts")

**Purpose:** How many live, active accounts a workspace has.

**Returns:** an `int`.

**Rules:**
- **R1.** Counts accounts of `workspace_id` with `is_active = True` and `is_deleted = False`: inactive accounts, soft-deleted accounts (also one still marked active) and other workspaces' accounts are not counted.
- **R2.** No cap: 107 live accounts → 107.
- **R3.** An unknown or empty workspace → `0`.

**Errors:** none · **Side effects:** none

---

## `AccountDAO.get_accounts_by_tag_id(db, *, workspace_id, tag_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AccountService.get_accounts_by_tag_id` ← `GET /accounts/by-tag/{tag_id}/`, after checking the tag exists in the workspace)

**Purpose:** One page of the live, active accounts that carry one tag.

**Returns:** a `list` of `Account` (possibly empty).

**Rules:**
- **R1.** Returns accounts of `workspace_id` with `is_active = True`, `is_deleted = False` and an assignment to `tag_id` recorded in `workspace_id`. Inactive and soft-deleted accounts are left out; an assignment recorded under another workspace never counts.
- **R2.** An unknown tag, `tag_id=0`, a tag with no live account, or another workspace → `[]`. The tag row is not read: only the assignment's `tag_id` is compared.
- **R3.** [BUG-1481] (HR-4) When the tag is deleted (`account_tags.is_active = False`), `[]` is returned; the assignments stay as they are and the accounts are listed again once the tag is active. *(Today: the tag is not looked at — the accounts of a deleted tag are returned.)*
- **R4.** [BUG-1480] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`. *(Today: no `ORDER BY`; plan-dependent.)*
- **R5.** `skip` / `limit` after the filters; defaults 0 and 100; `limit=0` → `[]`; negative values raise `DataError` as in `get_accounts_in_workspace`. Each account appears once (`uq_account_tag` allows one assignment per account and tag).

**Errors:** as `get_accounts_in_workspace`.

**Side effects:** none

---

## Inherited `BaseDAO` methods on `Account`
**Visibility:** public (used by: `get`, `create` with a dict, `update` with a dict ← `AccountManager`; `get_by_id_and_workspace` ← `AccountInvoiceManager` (create / update invoice), `PurchaseOrderManager` (change-log labels), `WorkOrderManager` (create / update), `SalesService` (invoice from order); `get_by_workspace`, `get_multi`, `remove`: no caller)

**Rules:**
- **R1.** `create` with a dict holding `workspace_id` and `name` gives `allow_invoices = True`, `is_active = True`, `is_deleted = False`, `created_at` from the database clock, every other field `NULL`. An `AccountCreate` cannot be passed directly: it carries `tag_ids`, which is not a column, so `create` raises `TypeError` (`'tag_ids' is an invalid keyword argument for Account`) and nothing is added (verified); it also has no `workspace_id`.
- **R2.** `update` with a dict sets any column given; the database sets `updated_at` when a row actually changes.
- **R3.** `get` and `get_by_id_and_workspace` are raw (HR-4 scope): they return soft-deleted and inactive accounts; `get` ignores the workspace; `get_by_id_and_workspace` returns `None` for another workspace's account (base spec). What each caller does with a deleted account is that caller's (FU-2).
- **R4.** [BUG-100] `get_by_workspace` and `get_multi` order by `id` ascending (base spec). *(Today: no order; fix in `app/dao/base.py`.)*
- **R5.** `remove` (no caller; nothing hard-deletes accounts today — they are soft-deleted) — intended at the DAO, stated as fact (decided by Claude under the reviewer's delegation (2026-11-03)): (a) an account with no invoice, order or tag assignment is hard-deleted and returned; (b) an account with a tag assignment raises `IntegrityError` with `NotNullViolation` (23502) at the flush: the ORM sets the assignments' `account_id` to `NULL` (the `tag_assignments` backref has no `passive_deletes`) before the database `ON DELETE CASCADE` can act; (c) an account referenced by an invoice raises `IntegrityError` with `NotNullViolation` (23502) for the same reason (the `invoices` backref); nothing is deleted in (b) or (c). In the database itself, a `DELETE` of an account an invoice or order references is refused with `RestrictViolation` (23001; the foreign keys are `ON DELETE RESTRICT`), and a `DELETE` of an account with only tag assignments cascades to them. *(Follow-up FU-3: a future hard delete needs `passive_deletes=True` on those backrefs, or the refusal must be translated; no bug.)*

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 15–42 | `search_by_name_in_workspace` | Not specified (P3) |
| 44–53 | keyword-only; defaults `name=None`, `tag_code=None`, `skip=0`, `limit=100` | `get_accounts_in_workspace` R2, R4, R10 |
| 68–72 | workspace, active, not deleted | `get_accounts_in_workspace` R1, R1a |
| 74 | `if name:` falsy / truthy (untrimmed) | `get_accounts_in_workspace` R2 |
| 75 | `ILIKE '%name%'` unescaped | `get_accounts_in_workspace` R3 |
| 77 | `if tag_code:` falsy / truthy | `get_accounts_in_workspace` R4 |
| 78–85 | join assignment (its `workspace_id`) and tag (exact code, no `is_active`, no tag workspace) | `get_accounts_in_workspace` R5, R6, R7, R9 |
| 87 | `DISTINCT`, offset / limit, no `ORDER BY` | `get_accounts_in_workspace` R7, R8, R10 |
| 89–98 | count with three filters | `count_active_accounts` R1, R2, R3 |
| 122–131 | join assignment; account and assignment workspace; `tag_id`; tag row not read | `get_accounts_by_tag_id` R1, R2, R3 |
| 132–135 | offset / limit, `DISTINCT`, no `ORDER BY` | `get_accounts_by_tag_id` R4, R5 |
| 138 | singleton | Not specified |
| `base.py` 43, 187–194 | raw lookups | inherited R3 |
| `base.py` 61–84, 108–119 | create / update | inherited R1, R2 |
| `base.py` 59, 161–167 | no order (BUG-100) | inherited R4 |
| `base.py` 136–139 | remove: unreferenced / assignment / invoice (ORM nulls the child key, 23502; SQL 23001) | inherited R5 |

## Gap log
- G1 (`account.notes.md` discrepancies, executor 2026-11-03) — Fact + Intent (decided by Claude under the reviewer's delegation (2026-11-03)) — re-verified (`v_gaps.py`): ORM `remove` of an account referenced by an invoice → 23502 (the backref nulls `account_id`), a SQL `DELETE` → 23001 `RestrictViolation`; ORM `remove` of an account with a tag assignment → 23502, SQL `DELETE` cascades. Inherited R5 rewritten as fact; intended at the DAO, no bug; FU-3 added. Status unchanged.
