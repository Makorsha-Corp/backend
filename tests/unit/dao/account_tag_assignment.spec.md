# Spec — `app/dao/account_tag_assignment.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1–P3 decided by Claude under the reviewer's delegation (2026-11-03), each by the matching decision of the approved item tag assignment DAO spec (`tests/unit/dao/item_tag_assignment.spec.md`). None of them is the owner's own answer. The house-rule lines stand. Decisions of the approved account manager spec are reused with their IDs (BUG-865, BUG-870).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. For account tags "deleted" is `is_active = False`; accounts are soft-deleted with `is_deleted`. Things of a soft-deleted parent are hidden by the parent's state, their own rows untouched ("hidden, not cascaded", 2026-10-11): an assignment row belongs to both its account and its tag. Raw lookups stay raw (HR-4 scope). Re-creating unchanged link rows is a bug (BUG-870, HR-9). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `v_asg.py`, `schema.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints (`uq_account_tag (account_id, tag_id)` across workspaces), indexes; `get_account_tag_dao` before and after the first call; `get_tags_for_account` with active, inactive, other-workspace and zero-count tags, a link recorded under the other workspace, a soft-deleted account, an unknown account, an unflushed link, the SQL (no `ORDER BY`, no `is_active`), and the order under a forced sequential scan changing after a tag update (`bravo, Alpha, alpha, Charlie` → `Alpha, alpha, Charlie, bravo`); `get_assignment` / `assignment_exists` in both workspaces; a second link for one pair under another workspace (`uq_account_tag`, 23505); `delete_assignment` own / other workspace / again (counter untouched); `remove_all_tags_from_account`: the count, every counter (3 → 2, inactive 2 → 1, other workspace's tag unchanged, 0 stays 0), the other workspace's link and another account's link kept, an unknown account → 0, an unflushed link (not counted, inserted by the method's flush), savepoint roll-back; inherited `create` (dict; schema → `NotNullViolation`). **Read, not run:** `AccountManager` (every caller). **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | "Is tag T on account A", "find / delete that link" do not look at whether the account or the tag is deleted | intended — raw lookups; the account manager decides (item tag assignment P1) | Claude, delegated |
| P2 | "Remove every tag of an account" exists only for the account save that re-creates unchanged tags | intended here; BUG-870 (existing) fixes the save, and this method then has no caller and is removed with that fix | Claude, delegated |
| P3 | Saving an account's tags erases its links to deleted tags (and lowers their counters) | bug — links to deleted tags are left alone (BUG-1487, per BUG-935); fixed in the account manager | Claude, delegated |

Decided by house rules: an account's tags include deleted tags (BUG-865, existing) and come back in no fixed order (BUG-1486, new).

### House-rule violations — applied automatically

- **HR-4** `get_tags_for_account` R3 — deleted (inactive) tags are returned as the account's tags (verified).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** BUG-865 (existing; its Module cell names this file). Rules: `get_tags_for_account` R3.
- **HR-6** `get_tags_for_account` R4 — no `ORDER BY`; every account response (`GET /accounts/`, `/accounts/{id}/`, `/accounts/by-tag/…`) shows the tag chips in whatever order the database produces (verified to change after a tag update). Intended: name case-insensitive ascending, then `id` ascending; system tags not grouped first (BUG-932 precedent for an item's tags).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1486 (pattern `unordered-pagination`; fix in this file). The approved account manager spec ruled the same order (P7) but cites **BUG-719**, which is an inventory bug: BUG-1486 is the register row for this fix. Rules: `get_tags_for_account` R4.
- **HR-6** inherited `get_by_workspace` — BUG-100 (existing). No caller.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-100 (existing). Rules: inherited R3.

Checked and **not** a new line here: **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-2** — one link per account and tag is enforced by `uq_account_tag`. **HR-9** — this DAO writes no audit stamp; re-stamping is the manager's (BUG-870). **HR-10** — no money, stock or approval. **HR-16** — every method filters on the link's own `workspace_id`; the tag's and the account's workspaces are not compared (R2 of `get_tags_for_account`); the API writes links only for tags it found in the caller's workspace.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. The link lookups do not look at the account's or the tag's state — ✅ intended
**Background:** `get_assignment`, `assignment_exists` and `delete_assignment` find the link by account, tag and workspace only. The manager checks the account and the tag before (assign refuses an inactive tag; BUG-863 makes it refuse a deleted account).
**What happens today:** A link to a deleted tag, or of a deleted account, is found, reported as existing and deletable. (Verified.)
**Example:** Deleted tag "Old vendor" is still on "Acme": "is Old vendor on Acme?" → yes.
**Rules affected:** `get_assignment` R3, `assignment_exists` R2, `delete_assignment` R3
**Answer:** intended — per item tag assignment DAO P1 (HR-4 scope).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged (✅).

### P2. "Remove every tag of an account" serves only the replace-all save — ✅ intended here
**Background:** Only caller: `AccountManager.update_account` with `tag_ids`, which removes every link and re-adds the list. The account manager spec ruled that a bug (BUG-870: staying tags keep their link). The item twin was handled the same way (item tag assignment DAO P2).
**What happens today:** Every link of the account in the workspace is deleted and each tag's counter lowered. (Verified.)
**Example:** Saving "Acme" with the same two tags deletes and re-creates both links.
**Rules affected:** none of this DAO — `remove_all_tags_from_account` does what its name says (R1–R6).
**Answer:** intended at the DAO — per BUG-870 / item tag assignment P2: the fix is in `AccountManager.update_account`, after which this method has no caller and is removed with that fix.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): BUG-870 (existing), no new ID; listed in `docs/testing/dead-code-removal-checklist.md` as "remove together with the fix of BUG-870", with `get_account_tag_dao`, which exists only for it. It is reachable today, so its rules stay and are tested as it behaves today.

### P3. Saving an account's tags erases its links to deleted tags — 🐞 BUG-1487
**Background:** A tag is deleted by `is_active = False`; its links stay, hidden from the account's tag list once BUG-865 is fixed, and come back if the tag is restored (`PUT /account-tags/{id}` with `is_active: true`). `remove_all_tags_from_account` deletes **every** link, including links to deleted tags, and lowers their counters (R2, R3). The user cannot re-send a tag the form does not show. BUG-870's fix ("only removed tags are deleted") does not say what a hidden tag is. The item twin was ruled a bug (BUG-935).
**What happens today:** After a save, the account has no link to any deleted tag, and that tag's counter has dropped by one. Restoring the tag later puts it back only on accounts nobody saved meanwhile. (DAO part verified.)
**Example:** Tag "Importer" is on 30 accounts and deleted by mistake. During the week 5 of them are edited. Support restores "Importer": it is on 25 accounts.
**Rules affected:** none of this DAO; `AccountManager.update_account` R11–R13 (account manager spec, FU-1).
**Answer:** bug — per BUG-935 precedent ("hidden, not cascaded"): a tag save touches only the account's links to **active** tags; links to deleted tags are left as they are (no counter change), hidden while the tag is deleted and shown again once it is restored. Fix in `AccountManager.update_account`, together with BUG-870.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1487 (pattern `replace-all-erases-hidden-rows`; logged against `app/managers/account_manager.py`). No rule of this DAO changes.

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Account manager** — spec approved (`tests/unit/managers/account_manager.spec.md`) | (a) `get_tags_for_account` R5 cites BUG-719 (an inventory bug); the register row for this order is BUG-1486 — the citation should be corrected in that spec and its cases. (b) `update_account` R11–R13 must add BUG-1487: links to deleted tags survive a save untouched; R12's counter changes apply to active tags only. (c) `delete_account` R6 (BUG-877) lowers every assigned tag's counter: whether deleted tags too follows BUG-1487 (they keep the link; their counter is not "live" anyway). **Status 2026-11-03:** (a) and (b) applied to the account manager spec (its Gap log C1, C2; R5 now BUG-1486, new R13a); (c) still open. | P3, HR-6 line |

## Overview
`AccountTagAssignmentDAO` reads and deletes rows of `account_tag_assignments`, the links that put a tag on an account inside one workspace. Its only caller is `AccountManager` (create / update / assign / unassign / list tags; the account services read tags through it). It protects workspace isolation through the link's own `workspace_id`. It validates nothing and never commits; `delete_assignment` and `remove_all_tags_from_account` flush, and the latter lowers tag counters through `AccountTagDAO.decrement_usage_count` (account tag spec).

**Callables:** 6 specified (+ 1 section on inherited behavior) · 1 not specified
**Externals to mock:** none. `assigned_at` is a Python default bound at import (not patchable).
**Integration-only behavior:** none.

**Model facts (table `account_tag_assignments`):** `id` PK; `workspace_id`, `account_id`, `tag_id` NOT NULL, each → its table ON DELETE CASCADE; `assigned_at` NOT NULL (Python `utcnow()`); `assigned_by` → `profiles`. Unique `uq_account_tag (account_id, tag_id)` — **the workspace is not part of it**: a second link for one pair under another workspace is refused too. Indexes on `id`, `account_id`, `tag_id`, `workspace_id`. Nothing ties the link's `workspace_id` to the account's or the tag's.

**Notes for the test designer:**
- Use the singleton `account_tag_assignment_dao`; every parameter after `db` is keyword-only.
- Build `Account`, `AccountTag`, `AccountTagAssignment` rows directly; flush before calling (`autoflush=False`). An unflushed link is invisible to every lookup here.
- **BUG-1486 (order):** today not deterministic (verified to change after an update under a forced sequential scan). Ids 1 "bravo", 2 "Alpha", 3 "alpha", 4 "Charlie" → intended 2, 3, 1, 4; **non-strict** xfail. Other cases compare **sets**.
- **Cross-workspace links** can only be built directly.
- `get_account_tag_dao` keeps its result in the module global `account_tag_dao`; to see the first-call branch, set `app.dao.account_tag_assignment.account_tag_dao = None` (monkeypatch) before calling.

## Not specified
- `account_tag_assignment_dao` — module-level singleton, no logic.

---

## `get_account_tag_dao()`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `remove_all_tags_from_account`)

**Purpose:** Hand out the account tag DAO without importing it at module load (circular import).

**Rules:**
- **R1.** Returns the singleton `app.dao.account_tag.account_tag_dao`.
- **R2.** When the module global `account_tag_dao` is `None`, it is set to that singleton by the first call; later calls return the stored object without importing again.

**Errors:** none · **Side effects:** sets the module global on the first call.

---

## `AccountTagAssignmentDAO.get_tags_for_account(db, *, account_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `AccountManager.get_tags_for_account` ← every account response of `AccountService`)

**Purpose:** The tags on one account.

**Returns:** a `list` of `AccountTag` (possibly empty).

**Rules:**
- **R1.** Returns every tag with a link to `account_id` recorded in `workspace_id`, each once. An unknown account or none → `[]`; a link recorded under another workspace is not returned (asking with that workspace returns only its links).
- **R2.** Only the link's workspace is compared: a tag of another workspace linked under this workspace is returned (HR-16 invalid data). The tag's `usage_count` and `is_system_tag` play no part.
- **R3.** [BUG-865] (HR-4) Only active tags are returned. *(Today: deleted tags too.)*
- **R4.** [BUG-1486] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending; system tags are not grouped first. *(Today: no `ORDER BY`.)*
- **R5.** The account's state is not looked at: the tags of a soft-deleted or inactive account are returned.

**Errors:** none · **Side effects:** none

---

## `AccountTagAssignmentDAO.get_assignment(db, *, account_id, tag_id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** internal (used by: `assignment_exists`, `delete_assignment`)

**Returns:** the `AccountTagAssignment`, or `None`.

**Rules:**
- **R1.** The link with that account, tag and workspace is returned; there is at most one (`uq_account_tag`), so no order is needed.
- **R2.** The same pair under another workspace, another tag or another account → `None`.
- **R3.** ✅ (P1) The account's and the tag's state are not looked at.

**Errors:** none · **Side effects:** none

---

## `AccountTagAssignmentDAO.assignment_exists(db, *, account_id, tag_id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `AccountManager._assign_tags_to_account`, `assign_tag`)

**Rules:**
- **R1.** `True` exactly when `get_assignment` finds a link (R1, R2 there); else `False`.
- **R2.** ✅ (P1) A link to a deleted tag, or of a deleted account, counts.

**Errors:** none · **Side effects:** none

---

## `AccountTagAssignmentDAO.delete_assignment(db, *, account_id, tag_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `AccountManager.unassign_tag`)

**Rules:**
- **R1.** When the link exists (as `get_assignment`), it is hard-deleted and flushed, and `True` is returned; a query in the same session no longer finds it.
- **R2.** No link (including the pair under another workspace) → `False`, nothing deleted; calling again after a delete → `False`.
- **R3.** ✅ (P1) Account and tag state are not looked at. The tag's `usage_count` is not touched (the manager lowers it).

**Errors:** none · **Side effects:** at most one row deleted, flushed.

---

## `AccountTagAssignmentDAO.remove_all_tags_from_account(db, *, account_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `AccountManager.update_account` with `tag_ids`; no caller once BUG-870 is fixed — P2)

**Purpose:** Remove every tag of an account and lower each tag's counter.

**Returns:** the number of links removed.

**Rules:**
- **R1.** Every link of `account_id` recorded in `workspace_id` is hard-deleted; the count is returned. Links of other accounts and links recorded under another workspace stay.
- **R2.** Links to deleted (inactive) tags are removed too (see P3 / BUG-1487 for the caller).
- **R3.** For each removed link, the tag's counter is lowered as `AccountTagDAO.decrement_usage_count` does with this `workspace_id`: −1, never below 0; a tag of another workspace is not found and keeps its counter (its link is still removed). Given counters Zulu 3, deleted Old 2, other-workspace W2 5, Zero 0 → 2, 1, 5, 0.
- **R4.** No link → `0`, nothing changes.
- **R5.** A link added to the session but not yet flushed is not counted and not removed; the method's flush inserts it.
- **R6.** Flushed, not committed: a savepoint roll-back restores the links and counters. Tags and accounts are otherwise untouched.

**Errors:** none · **Side effects:** links deleted, counters lowered, flushed.

---

## Inherited `BaseDAO` methods on `AccountTagAssignment`
**Visibility:** public (used by: `create` with a dict ← `AccountManager`; others: no caller)

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `account_id`, `tag_id` gives `assigned_at` set (assert only "set"), `assigned_by` `None` unless given. An `AccountTagAssignmentCreate` has no `workspace_id` → `IntegrityError` (`NotNullViolation`, 23502).
- **R2.** A second link for the same `(account_id, tag_id)` — in this or another workspace — raises `IntegrityError` (`UniqueViolation`, 23505, `uq_account_tag`). Unknown account, tag or workspace → `ForeignKeyViolation` (23503).
- **R3.** [BUG-100] `get_by_workspace` / `get_multi` ordered by `id` ascending (base spec). *(Today: no order.)*
- **R4.** A hard delete of the account, the tag or the workspace deletes its links (cascade).

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 11 | module global `None` at import | `get_account_tag_dao` R2 |
| 16–19 | global `None` → import and store / stored → return | `get_account_tag_dao` R1, R2 |
| 39–47 | join tags; link workspace + account; no `is_active`, no order, no tag workspace | `get_tags_for_account` R1–R5 |
| 64–72 | three filters, `.first()` | `get_assignment` R1–R3 |
| 89–92 | `is not None` | `assignment_exists` R1, R2 |
| 109–116 | found → delete, flush, `True` / `False` | `delete_assignment` R1–R3 |
| 133–140 | all links of the account in the workspace | `remove_all_tags_from_account` R1, R2, R5 |
| 142 | lazy DAO | `get_account_tag_dao` R1 |
| 144–147 | loop zero / many: decrement (workspace-scoped, floor 0), delete | `remove_all_tags_from_account` R3, R4 |
| 148–149 | flush, return count | `remove_all_tags_from_account` R1, R4, R5, R6 |
| 152 | singleton | Not specified |
| `base.py` 61–84 | create | inherited R1, R2 |
| `base.py` 59, 161–167 | no order (BUG-100) | inherited R3 |
