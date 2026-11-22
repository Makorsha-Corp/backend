# Spec — `app/dao/account_tag.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1–P5 decided by Claude under the reviewer's delegation (2026-11-03), each by the matching decision of the approved item tag DAO spec (`tests/unit/dao/item_tag.spec.md`; this file is its near copy). None of them is the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. For account tags "deleted" is `is_active = False` (the model calls it "Soft delete"; `AccountTagService.delete_tag` sets only that; there is no `is_deleted`). Soft-deleted rows do not show up in lists. Raw lookups and raw writes stay raw (HR-4 scope; item tag DAO P1, P2). Hidden caps are bugs (BUG-342, BUG-982). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway script `v_tag.py`, plus `schema.py`, with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, defaults (none in the database), constraints, indexes (no unique index); `get_by_tag_code_in_workspace` for the own workspace, another workspace, an unknown workspace, an inactive tag, `Supplier`, `" supplier"`, `sup`, `sup%`, `None`, a positional call (`TypeError`); `get_active_tags_in_workspace` (inactive left out; 102 tags → 100, `limit=1000` → 102; the SQL has no `ORDER BY`; under a forced sequential scan, system tag "Zed" came back last, and after an update the order changed from `Zulu, apple, Banana, Zed` to `apple, Banana, Zed, Zulu`); `get_system_tags_in_workspace` (an inactive system tag **is** returned; no `ORDER BY`; other / unknown workspace `[]`); both counters: own workspace, other workspace, unknown id, inactive tag, `0`, negative stored value, the returned object, the stale loaded object (loaded 3 / stored 10 → increment stores 4; loaded 3 / stored 0 → decrement stores 2; expired object → 11), the flush carrying another pending change, savepoint roll-back; inherited `create` defaults. **Read, not run:** `AccountTagService`, `AccountManager` (counter callers), `seed_default_account_tags`, `GET /account-tags/` description. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | "Find the tag with code X" also finds a deleted tag | intended — raw lookup (item tag P1); what "create tag" does with it is the account tag service's | Claude, delegated |
| P2 | A deleted tag's account counter still goes up and down | intended — raw write (item tag P2); the account manager must stop attaching deleted tags (BUG-629) | Claude, delegated |
| P3 | The counter is changed from the number last read, so changes made at the same moment can be lost | bug — changed in the database in one step (BUG-1484, per BUG-931) | Claude, delegated |
| P4 | Counting for a tag that does not exist silently does nothing | intended — callers check the tag first (item tag Q2) | Claude, delegated |
| P5 | The account tag list silently stops at 100 tags | bug — every tag is returned (BUG-1485); the unused paging options go with the fix | Claude, delegated |

Decided by house rules: the two tag lists have no sort order, and "system tags first", promised by `GET /account-tags/`, does not happen (BUG-1482); the system tag list shows deleted system tags (BUG-1483).

### House-rule violations — applied automatically

- **HR-6** `get_active_tags_in_workspace` R4, `get_system_tags_in_workspace` R3 — no `ORDER BY` in either. `GET /account-tags/` documents "sorted with system tags first"; verified: a system tag came back last, and an update reordered the list. Intended: active list — system tags first, then name case-insensitive ascending, then `id` ascending (BUG-930 precedent for item tags); system list — name case-insensitive ascending, then `id` ascending (BUG-929 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1482 (pattern `unordered-pagination`; both lists, one fix in this file). Rules: `get_active_tags_in_workspace` R4, `get_system_tags_in_workspace` R3.
- **HR-4** `get_system_tags_in_workspace` R2 — the list does not filter `is_active`: a deleted system tag is returned (verified). Its item-tag twin filters it. Through the API a system tag cannot be deleted (update / delete answer 403), so only data written outside the API reaches this today.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1483 (pattern `list-returns-soft-deleted`; fix in this file). Rules: `get_system_tags_in_workspace` R2.
- **HR-6** inherited `get_by_workspace` — BUG-100 (existing; the fix in `app/dao/base.py` reaches this DAO). No caller.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-100 (existing). Rules: inherited R4.

Checked and **not** a new line here: **HR-4** — `get_active_tags_in_workspace` leaves deleted tags out; the code lookup and the counters are raw (P1, P2). **HR-5** — the cap of P5 is not filtering after paging; every filter is in the query. **HR-7, HR-8** — no `limit` from the API, no `LIKE`. **HR-1, HR-2, HR-3** — no name or code is written or compared for uniqueness here; that `account_tags` has no unique index and that names are never checked are account tag service matters (FU-1). **HR-9** — no "last changed by" column. **HR-10** — a usage counter is not money, stock or an approval (P3 asks for a one-statement update, not a lock). **HR-16** — every method filters on the tag's `workspace_id`.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. "Find the tag with code X" also finds a deleted tag — ✅ intended
**Background:** Only caller: `AccountTagService.create_tag`, which answers 409 `Tag with code '<code>' already exists` when anything is found. Item tag DAO P1 ruled the same lookup raw.
**What happens today:** A deleted tag is found like an active one. (Verified.)
**Example:** Tag "Vendor" (`vendor`) is deleted; creating "Vendor" again answers 409 although no such tag is listed.
**Rules affected:** `get_by_tag_code_in_workspace` R3
**Answer:** intended — per item tag DAO P1 (HR-4 scope); whether a deleted tag's code may be reused is the account tag service's (FU-1 (a)).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rule unchanged (R3 ✅).

### P2. A deleted tag's counter still changes — ✅ intended
**Background:** The counters are called by `AccountManager` (assign / unassign / create / update) and by `remove_all_tags_from_account`. The manager accepts deleted tags on create / update today (BUG-629).
**What happens today:** Increment and decrement work on an inactive tag (verified: 0 → 1).
**Example:** Deleted tag "Old vendor" is attached through `POST /accounts/` with `tag_ids: [7]`; its counter rises.
**Rules affected:** `increment_usage_count` R3, `decrement_usage_count` R5
**Answer:** intended — per item tag DAO P2: raw write; refusing deleted tags is the manager's (BUG-629).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged (R3 ✅, R5 ✅).

### P3. The counter can lose changes made at the same moment — 🐞 BUG-1484
**Background:** `usage_count` is "number of accounts with this tag", shown on the tag list. Both counters add or subtract **in Python** on the loaded object and write the number back. Item tag DAO Q1 ruled the identical code a bug (BUG-931).
**What happens today:** Loaded 3 / stored 10 → increment stores 4; loaded 3 / stored 0 → decrement stores 2. (Verified.)
**Example:** Two users each tag an account "Supplier" (counter 5) at the same second; both write 6. The counter says 6 for ever, though 7 accounts carry the tag.
**Rules affected:** `increment_usage_count` R5, `decrement_usage_count` R6
**Answer:** bug — per BUG-931 precedent: the change is applied in the database relative to the stored value (`usage_count + 1`; `usage_count - 1` only where it is above 0), and the returned tag shows the stored result; no row lock.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1484 (pattern `non-atomic-counter-update`). Rules: `increment_usage_count` R5, `decrement_usage_count` R6 (tagged).

### P4. Counting for a tag that does not exist does nothing — ✅ intended
**Background:** Both counters are annotated "returns the updated tag"; given an unknown id or another workspace's tag they return `None` without error. Callers pass tags they have just found in the workspace.
**What happens today:** `None`, nothing written. (Verified.)
**Example:** A wrong id passed by a developer is silently ignored.
**Rules affected:** `increment_usage_count` R2, `decrement_usage_count` R4
**Answer:** intended — per item tag DAO Q2; the annotation should say `AccountTag | None` when the file is next touched (no bug).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged (R2 ✅, R4 ✅).

### P5. The account tag list silently stops at 100 tags — 🐞 BUG-1485
**Background:** `get_active_tags_in_workspace` has `skip=0`, `limit=100`; its only caller (`AccountTagService.get_tags` ← `GET /account-tags/`, the tag picker of the account screens) passes neither and the endpoint has no paging. Hidden caps were ruled bugs (BUG-982, BUG-1437). Its item-tag twin has no cap.
**What happens today:** Of 102 active tags, 100 come back, with no order (BUG-1482), so which are missing changes. (Verified; `limit=1000` → 102.)
**Example:** A workspace with 120 tags cannot pick 20 of them on the account form, and the missing 20 vary.
**Rules affected:** `get_active_tags_in_workspace` R2
**Answer:** bug — per BUG-982 precedent: every active tag is returned, no cap; the never-passed `skip` / `limit` go with the fix.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1485 (pattern `silent-result-cap`). The two parameters are listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` ("remove together with the fix of BUG-1485"). Rules: `get_active_tags_in_workspace` R2 (tagged).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Account tag service** (`app/services/account_tag_service.py`) — not yet described | (a) `create_tag` checks duplicates with the raw code lookup (P1): a deleted tag's code blocks reuse for ever (HR-2: deleted rows do not count). (b) `account_tags` has **no unique index**: code uniqueness is Python-only (`python-only-uniqueness`, BUG-895 precedent). (c) Names are never checked or trimmed (HR-1, HR-2). (d) `AccountTagCreate.tag_code` has no pattern (the item twin has `^[a-z0-9_]+$`): `"Supplier"` can be stored, which BUG-861's case-insensitive filter then matches; `AccountTagUpdate` lets a user tag change its `tag_code` with no duplicate check. (e) `update_tag` / `delete_tag` use the raw lookup: a deleted tag can be edited or deleted again (BUG-863 precedent); `is_active: true` through `PUT` restores it. (f) `GET /account-tags/system/` — whether the web app uses it. | P1, P5 |
| FU-2 | **Account manager** — spec approved | Every counter change inherits BUG-1484. | P3 |
| FU-3 | **Any future hard delete of tags** | The ORM nulls `account_tag_assignments.tag_id` before the database cascade (inherited R6): add `passive_deletes=True` to `AccountTag.account_assignments`. | inherited R6, G1 |

## Overview
`AccountTagDAO` reads and writes `account_tags`, the labels that say what an account is (Supplier, Client, Utility, … seeded as system tags by `seed_default_account_tags`; users add their own). Callers: `AccountTagService` (`GET /account-tags/`, `GET /account-tags/system/`, create / update / delete tag) and `AccountManager` (the counters, the inherited `get_by_id_and_workspace`). It protects workspace isolation and keeps deleted tags out of the tag lists. It validates nothing, checks no uniqueness and never commits; the counters flush.

**Callables:** 5 specified (+ 1 section on inherited behavior) · 2 not specified
**Externals to mock:** none. `created_at` is a Python default (`app.utils.time.utcnow`, bound at import; patching does not reach it).
**Integration-only behavior:** none.

**Model facts (table `account_tags`, class `app.models.account_tag.AccountTag`):** `id` PK; `workspace_id` NOT NULL → `workspaces` ON DELETE CASCADE; `name` varchar(100) NOT NULL; `tag_code` varchar(50) NOT NULL; `color` varchar(7); `icon` varchar(50); `description` text; `is_system_tag` (default `False`), `is_active` (default `True`, the soft-delete flag), `usage_count` (default `0`, no check constraint) — all NOT NULL with Python defaults only; `created_at` NOT NULL, Python `utcnow()`; `created_by` → `profiles`. Indexes: primary key, `ix_account_tags_id`, `ix_account_tags_workspace_id`; **no unique index** on `tag_code` or `name`; no check constraint; no trigger. `account_tag_assignments.tag_id` → `account_tags.id` ON DELETE CASCADE. Test database collation `English_United States.1252`.

**Notes for the test designer:**
- Use the singleton `account_tag_dao`. Every parameter after `db` is keyword-only (positional call → `TypeError`).
- Build `AccountTag(workspace_id, name, tag_code, …)` directly; flush before calling (`autoflush=False`).
- **Stored counter:** read it with a fresh SQL query after a counter call, not only from the returned object.
- **BUG-1484 (stale object):** flush the tag with `usage_count=3`, run `UPDATE account_tags SET usage_count = 10 …` without expiring the object, call the counter. Intended: 11 (decrement: 9; stored 0 → stays 0); today 4 (decrement 2). **Strict** xfail. Control: `db.expire(tag)` first → 11 today (plain pass).
- **BUG-1482 (order):** today's order is not deterministic (verified to change after an update under a forced sequential scan). Make the intended order differ from `id` ascending and descending, put a system tag last by `id`, plain ASCII names; **non-strict** xfail. Every other case compares **sets** of ids.
- **BUG-1485:** 101 active tags (`add_all`), no arguments → intended 101, today 100 → **strict** xfail.
- **BUG-1483:** an inactive system tag can only be built directly; today it is returned deterministically → **strict** xfail.

## Not specified
- `account_tag_dao` — module-level singleton, no logic.
- (`get_active_tags_in_workspace`'s `skip` and `limit` parameters — never passed; to be removed with BUG-1485 (P5). Their effect today is R2.)
- Inherited `BaseDAO` methods — base spec; only what is specific to `AccountTag` is stated below.

---

## `AccountTagDAO.get_by_tag_code_in_workspace(db, *, workspace_id, tag_code)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `AccountTagService.create_tag` ← `POST /account-tags/`, as the duplicate check: anything found → 409)

**Purpose:** The tag of a workspace that has a given code, if any.

**Returns:** the `AccountTag`, or `None`.

**Rules:**
- **R1.** Given a tag of the workspace with exactly that code, it is returned; a tag of another workspace with that code never is; an unknown workspace → `None`.
- **R2.** Exact comparison: for stored `supplier`, the codes `Supplier`, `" supplier"`, `sup` and `sup%` return `None`; `None` returns `None`.
- **R3.** ✅ (P1) A deleted tag (`is_active = False`) is returned like an active one; `is_system_tag` does not matter.
- **R4.** Given two tags of the workspace with one code (nothing prevents it), one of them is returned, which one is not specified. The only caller tests for "found / not found". Tests assert only that the result is one of them.

**Errors:** none · **Side effects:** none

---

## `AccountTagDAO.get_active_tags_in_workspace(db, *, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `AccountTagService.get_tags` ← `GET /account-tags/`, with no paging)

**Purpose:** Every tag of a workspace that is not deleted, system tags first.

**Returns:** a `list` of `AccountTag` (possibly empty).

**Rules:**
- **R1.** Returns the tags of `workspace_id` with `is_active = True`, system and user tags alike. Deleted tags and other workspaces' tags never; an unknown or empty workspace → `[]`.
- **R2.** [BUG-1485] (P5) Every matching tag is returned: given 101 active tags, 101. *(Today: at most 100 — `limit=100` by default and never passed.)*
- **R3.** [BUG-1482] (HR-6) Every system tag comes before every user tag. *(Today: no ordering; verified a system tag last.)*
- **R4.** [BUG-1482] (HR-6) Within each group, name case-insensitive ascending, then `id` ascending: user tags "bravo", "Alpha" (lower id), "alpha", "Charlie" come back "Alpha", "alpha", "bravo", "Charlie". *(Today: no `ORDER BY`; the order changed after an update.)*

**Errors:** none · **Side effects:** none

---

## `AccountTagDAO.get_system_tags_in_workspace(db, *, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `AccountTagService.get_system_tags` ← `GET /account-tags/system/`)

**Purpose:** The system (seeded) tags of a workspace.

**Returns:** a `list` of `AccountTag` (possibly empty).

**Rules:**
- **R1.** Returns tags of `workspace_id` with `is_system_tag = True`; user tags and other workspaces' tags never; unknown workspace or none → `[]`. No limit.
- **R2.** [BUG-1483] (HR-4) A deleted system tag (`is_active = False`) is not returned. *(Today: returned.)*
- **R3.** [BUG-1482] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending ("Utility", "client", "Bank" → "Bank", "client", "Utility"). *(Today: no `ORDER BY`.)*

**Errors:** none · **Side effects:** none

---

## `AccountTagDAO.increment_usage_count(db, *, tag_id, workspace_id)`
**Shape:** update (counter) · **Persistence:** writes · **Visibility:** public (used by: `AccountManager._assign_tags_to_account`, `assign_tag`)

**Purpose:** Count one more account for a tag.

**Returns:** the `AccountTag` (the session's instance), or `None`.

**Rules:**
- **R1.** A tag with that id in that workspace: stored `usage_count` + 1 (2 → 3), the same instance is returned.
- **R2.** ✅ (P4) Unknown id or another workspace's tag → `None`, nothing written, no error.
- **R3.** ✅ (P2) A deleted tag and a system tag are counted like any other.
- **R4.** No bound and no sign check: a stored −2 becomes −1.
- **R5.** [BUG-1484] (P3) The increase applies to the value stored at that moment: loaded object 3 / stored 10 → stored 11, returned tag shows 11. *(Today: 4 is stored and returned. With a freshly loaded or expired object: 11 already.)*
- **R6.** Flushed, not committed: a savepoint roll-back around the call restores the old value. The flush also writes any other pending change of the session (verified: an unflushed rename of the tag is saved with it).

**Errors:** none · **Side effects:** at most one row's `usage_count`, flushed.

---

## `AccountTagDAO.decrement_usage_count(db, *, tag_id, workspace_id)`
**Shape:** update (counter) · **Persistence:** writes · **Visibility:** public (used by: `AccountManager.unassign_tag`; `AccountTagAssignmentDAO.remove_all_tags_from_account`, once per assignment)

**Purpose:** Count one account less for a tag, never below zero.

**Returns:** the `AccountTag`, or `None`.

**Rules:**
- **R1.** A tag of the workspace with `usage_count` above 0: stored − 1 (3 → 2, 1 → 0); the tag is returned.
- **R2.** `usage_count = 0`: nothing written, the tag is returned with 0, nothing is flushed.
- **R3.** A negative stored value: nothing written, returned unchanged (−2).
- **R4.** ✅ (P4) Unknown id or another workspace's tag → `None`, nothing written, no error.
- **R5.** ✅ (P2) A deleted tag and a system tag are decremented like any other.
- **R6.** [BUG-1484] (P3) The decrease and the "not below 0" check use the value stored at that moment: loaded 3 / stored 10 → 9; loaded 3 / stored 0 → stays 0; the returned tag shows it. *(Today: 2 in both cases.)*
- **R7.** When written: flushed, not committed (as `increment_usage_count` R6).

**Errors:** none · **Side effects:** at most one row's `usage_count`, flushed when changed.

---

## Inherited `BaseDAO` methods on `AccountTag`
**Visibility:** public (used by: `create` with a dict, `update` with an `AccountTagUpdate` or `{"is_active": False}`, `get_by_id_and_workspace` ← `AccountTagService`; `get_by_id_and_workspace` ← `AccountManager`, `AccountService`, the counters; `get`, `get_by_workspace`, `get_multi`, `remove`: no caller)

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `name`, `tag_code` gives `is_system_tag = False`, `is_active = True`, `usage_count = 0`, `created_at` set (naive UTC, assert only "set"), `created_by` / `color` / `icon` / `description` `None`. An `AccountTagCreate` has no `workspace_id` (`NotNullViolation`).
- **R2.** `create` checks no uniqueness: a second tag with the same `tag_code` or `name` is saved (FU-1 (b)).
- **R3.** `update` with an `AccountTagUpdate` applies only fields set to a value (base spec `update` R2, R3); with a dict any column, including `{"is_active": False}` (the service's delete) and `{"is_active": True}`.
- **R4.** [BUG-100] `get_by_workspace` / `get_multi` ordered by `id` ascending (base spec). *(Today: no order.)*
- **R5.** Raw lookups return deleted tags (HR-4 scope).
- **R6.** `remove` (no caller; tags are only soft-deleted today) — intended at the DAO, stated as fact (decided by Claude under the reviewer's delegation (2026-11-03)): a tag with no assignment is hard-deleted and returned; a tag with an assignment raises `IntegrityError` with `NotNullViolation` (23502) at the flush, because the ORM sets the assignments' `tag_id` to `NULL` (the `account_assignments` backref has no `passive_deletes`) before the database `ON DELETE CASCADE` can act; nothing is deleted. A `DELETE` in SQL cascades to the assignments. *(Follow-up FU-3: a future hard delete needs `passive_deletes=True`; no bug.)*

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13–15, 36–38, 62–64, 84–86, 104–106 | keyword-only parameters | Notes |
| 27–32 | workspace + exact code; no `is_active` | `get_by_tag_code_in_workspace` R1, R2, R3 |
| 33 | `.first()`, no order; one of duplicates | `get_by_tag_code_in_workspace` R1, R4 |
| 37 | `skip=0`, `limit=100` never passed (BUG-1485) | `get_active_tags_in_workspace` R2; Not specified |
| 51–56 | workspace + `is_active` | `get_active_tags_in_workspace` R1 |
| 57–59 | offset / limit, no `ORDER BY` (BUG-1482) | `get_active_tags_in_workspace` R2, R3, R4 |
| 75–80 | workspace + `is_system_tag`; no `is_active` (BUG-1483) | `get_system_tags_in_workspace` R1, R2 |
| 81 | `.all()`, no `ORDER BY` (BUG-1482) | `get_system_tags_in_workspace` R1, R3 |
| 98 | raw lookup in workspace | `increment_usage_count` R1, R2, R3 |
| 99 | `if tag:` | `increment_usage_count` R1, R2 |
| 100–101 | `+= 1` on loaded value (BUG-1484), flush | `increment_usage_count` R4, R5, R6 |
| 118 | raw lookup in workspace | `decrement_usage_count` R4, R5 |
| 119 | `tag and usage_count > 0`: none / 0 / negative / positive (loaded value) | `decrement_usage_count` R1, R2, R3, R4, R6 |
| 120–122 | `-= 1`, flush, return | `decrement_usage_count` R1, R6, R7 |
| 125 | singleton | Not specified |
| `base.py` 61–84, 108–119 | create / update | inherited R1, R2, R3 |
| `base.py` 59, 161–167 | no order (BUG-100) | inherited R4 |
| `base.py` 43, 187–194 | raw lookups | inherited R5 |
| `base.py` 136–139 | remove: no assignment / assignment (ORM nulls `tag_id`, 23502) | inherited R6 |

## Gap log
- G1 (`account_tag.notes.md` discrepancy, executor 2026-11-03) — Fact + Intent (decided by Claude under the reviewer's delegation (2026-11-03)) — re-verified (`v_gaps.py`): ORM `remove` of a tag with an assignment → 23502 (the backref nulls `tag_id` before the cascade). Inherited R5 split; new R6 states it as fact, intended at the DAO, no bug; FU-3 added. Status unchanged.
