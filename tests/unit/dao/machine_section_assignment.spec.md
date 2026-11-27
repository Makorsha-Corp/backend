# Spec — `app/dao/machine_section_assignment.py`

> **Status:** APPROVED (2026-10-16)
> **Source commit:** e48a092

> **Review round 2026-10-16.** The reviewer delegated every open decision of this spec to Claude. Decided by Claude under the reviewer's delegation (2026-10-16): every suggested answer is accepted — P1 (bug, BUG-907), P2 (intended), P3 (bug, BUG-908), Q1 (intended), Q2 (intended) and the house-rule lines BUG-906, BUG-907 (precedent line P1) and BUG-909. None of these is the reviewer's own answer. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed. Consequence of P3: once BUG-908 is fixed, this DAO's `clear_for_section` and `get_by_section` and `MachineSectionAssignmentManager.clear_for_section` have no caller; they are listed in `docs/testing/dead-code-removal-checklist.md` as "remove together with the fix of BUG-908". They are reachable today, so their rules stay and are tested as they behave today; BUG-907 stays logged and goes away with that removal.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10). Assignment rows have no soft-delete column of their own; the decision concerns the machines and sections they point at (P2).
> 2. Things belonging to a soft-deleted factory or section are **hidden by the parent's state, their own rows untouched**, so that restoring the parent brings them back ("hidden, not cascaded" — machine DAO P1 / P2, factory section DAO; confirmed 2026-10-11). An assignment row *belongs to* its section. Today the application's "delete section" hard-deletes the section's assignment rows through this DAO's `clear_for_section` — that conflicts with this decision and is raised as P3 (the fix is in the caller, not here).
> 3. "Whitespace" means what Python's `str.strip()` removes. (No rule of this DAO handles text; recorded for the follow-ups.)
> 4. Raw DAO lookups returning rows that point at deleted things are intended; the manager decides what to hide (base DAO spec, HR-4 scope).
>
> **Pilot convention:** every question below carried a suggested answer, applied to the rules as a provisional default. All were accepted on 2026-10-16 (decided by Claude under the reviewer's delegation); nothing is provisional any more.
>
> **Verified by running** (throwaway scripts against the test database, rolled back): every "Today:" note below; the table's columns, defaults, constraints, constraint names and indexes (no triggers); `get_by_machine` for the own workspace, another workspace and a machine without assignment; `get_by_section` workspace filtering (including a row of another workspace pointing at the same section), that it returns rows of soft-deleted machines and of a soft-deleted section, its default of 500 rows (10 001 rows present → 500; `limit=501` → 501), `limit=0`, `skip` past the end, negative `limit` / `skip` with their error classes and codes; `upsert_for_machine` creating a row (columns written and left empty), re-saving the same section (new `id`, `created_by` = the new user, one row only, `created_at` equal within one transaction), changing the section, clearing with `None` (with and without an existing row), accepting a section of another factory, a soft-deleted section, a section of another workspace, a soft-deleted machine and a machine of another workspace, the unique violation when the machine's existing row is in another workspace, the foreign-key violations on machine, section, user and workspace with their constraint names, the old row being back after a savepoint rollback of each failure, `user_id=None`, keyword-only arguments; that a machine whose `section_assignment` was already loaded still reports the old section after `upsert_for_machine` and after `clear_for_section` until it is expired; that a later flush of that machine does not bring the old row back; `clear_for_section` returning the machine ids, deleting rows of soft-deleted machines, leaving rows of other sections and other workspaces, the section row and the machine rows untouched, savepoint rollback, the empty case; the 10 000 cap (10 001 rows → 10 000 ids returned, 1 row left; a second call removes it); the application's "delete section" followed by the section DAO's `restore` (assignment rows gone, the restored section has no machines); the inherited `create` (schema → `NotNullViolation` on `workspace_id`; dict works), `update` with a dict, `get_by_workspace`, `get_by_id_and_workspace`. **Not run:** anything at the HTTP level; the *intended* behavior of the bug rules. **Row order:** never relied on — today's order of `get_by_section` / `clear_for_section` is unspecified (see Notes for the test designer).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted (decided by Claude under the reviewer's delegation, 2026-10-16)
| # | What the code does today | Answer (accepted) |
|---|---|---|
| P1 | "Unassign every machine of a section" handles at most 10 000 machines; any machine beyond that silently keeps its assignment, and which ones are left differs from run to run | bug — every assignment of the section is handled, no cap (same decision as "at most 1000 machines get a work order", BUG-342) — BUG-907. P3 is accepted, so the method loses its only caller once BUG-908 is fixed and goes away with this cap (dead-code list) |
| P2 | The two lookups of this file ("the assignment of machine X", "the assignments of section Y") also return assignments of deleted machines and assignments to deleted sections | intended — these are raw lookups; the manager decides what to hide (same decision as for every other DAO) |
| P3 | Deleting a section permanently erases the link of every machine to that section. If the section is restored later, it comes back empty: the machines are no longer in it | bug — deleting a section must leave the links alone; the machines are hidden with the section and come back when it is restored (the "hidden, not cascaded" decision of 2026-10-11). The change is in the section manager's delete, which must stop calling "unassign every machine of a section" — BUG-908 |
| Q1 | A comment in the code says "unassign every machine of a section" refreshes machines already loaded in memory. It does not: such a machine still reports its old section until it is reloaded. Both callers reload it themselves, so nobody sees a wrong value today | intended — reloading is the caller's job (both callers already do it); only the comment is wrong. No bug logged |
| Q2 | Moving a machine to another section throws the old link away and writes a new one; the link then shows who moved it and when, and its "last changed by / at" fields are never filled | intended — the link records who put the machine into its current section and when; "last changed" stays empty |

Already decided by house rules / existing bugs (kept as applied — decided by Claude under the reviewer's delegation, 2026-10-16):
- "the assignments of section Y" has **no sort order** → BUG-906 (new; fix in this file). It decides which rows the 10 000 cap leaves behind (P1).
- Saving a machine with **the section it already has** throws its link away and writes a new one (new id, "created by" = whoever saved) → BUG-909 (new; HR-9, same root cause as BUG-870 for account tags; fix in this file).
- "all assignments of a workspace" (the generic list, inherited, unused on this DAO) has no sort order → BUG-100 (already logged; the fix in `app/dao/base.py` reaches assignments, nothing to do in this file).

### House-rule violations — applied automatically
> All three lines kept as applied — decided by Claude under the reviewer's delegation (2026-10-16).

- **HR-6** `get_by_section` R6 — no sort order; paging with `skip` / `limit` can repeat or skip rows, and, through `clear_for_section` (P1), which assignments survive the 10 000 cap is whatever the database produces. Intended: `id` ascending before `skip` / `limit` (assignment rows have no name; HR-6's tie-break is the whole order). This is the DAO's own query (not inherited), so BUG-100 does not cover it — same situation as the factory section DAO's `get_by_factory` (BUG-903) and the machine DAO's lookups (BUG-343).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-906 (pattern `unordered-pagination`; the fix is in `app/dao/machine_section_assignment.py`) — decided by Claude under the reviewer's delegation (2026-10-16). Rules: `get_by_section` R6, `clear_for_section` R7. (Goes away with `get_by_section` if that method is removed after the BUG-908 fix.)
- **HR-9** `upsert_for_machine` R3 — saving a machine with the section it already has deletes its assignment row and inserts a new one: new `id`, `created_by` = the saving user, `created_at` = now, although nothing changed. The machine edit form re-sends the section on every save (`MachineManager.update_machine` calls the assignment manager whenever `factory_section_id` is in the request), so every edit of a machine re-stamps its link. Intended: when the machine already has exactly that section, the row is left untouched (same `id`, `created_by`, `created_at`) and returned. Same root cause as BUG-870 (account tags deleted and re-created on every save, ruled under HR-9).
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-909 (pattern `unchanged-rows-recreated`, per BUG-870; the fix is in `app/dao/machine_section_assignment.py`) — decided by Claude under the reviewer's delegation (2026-10-16). Rules: `upsert_for_machine` R3.
- **HR-6** inherited `get_by_workspace` (inherited methods R3) — no sort order. Intended for this raw lookup: `id` ascending before `skip` / `limit` (HR-6: "generic `BaseDAO` lists only guarantee `id` ascending"). `DAOMachineSectionAssignment` does not override it, so the BUG-100 fix in `app/dao/base.py` reaches assignments with nothing to change in this file. It has no caller on this DAO.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, pattern `unordered-pagination`, logged against `app/dao/base.py`) — no new ID. Rules: inherited methods R3.

Checked and **not** violated: **HR-5** — `get_by_section` applies its section and workspace filters in the query before `skip` / `limit`. **HR-4** — no method of this file is a list shown to users; the assignment table has no soft-delete column, and the rows pointing at deleted machines / sections are returned by raw lookups (P2). **HR-2** — "one section per machine" is enforced in the database (unique index on `machine_id`). **HR-10** — no money, stock or approval: no lock. **HR-14** — `clear_for_section` is not a background batch. House rules do not speak about caps on bulk operations, so P1 is a precedent match (`silent-result-cap`), not a house-rule line.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-10-16)

### P1. "Unassign every machine of a section" stops at 10 000 — 🐞 BUG-907
**Background:** A machine can be assigned to at most one section of its factory; the link is a row of its own (an "assignment"). `clear_for_section` removes the assignment rows of one section. It reads them through `get_by_section` with `limit=10000`, in no particular order (BUG-906). Its only caller is "delete section" (see P3).
**What happens today:** At most 10 000 rows are removed. Any further assignment row of the section is left in place, nothing tells the caller, and the returned list of machine ids is short. Which rows are left is decided by the database. (Verified: 10 001 assignments → 10 000 ids returned, 1 row left; a second call removes it.)
**Example:** A plant with 10 050 sensors registered as machines in section "Line A" deletes "Line A". 50 machines still say "section: Line A" — a deleted section — and the machine list's section filter still finds them by its id (machine DAO BUG-889).
**Rules affected:** `clear_for_section` R4 (tagged)
**Answer:** bug — per BUG-342 precedent (`silent-result-cap`): every assignment row of the section in the workspace is removed and its machine id returned, however many there are; no cap. If P3 is accepted, `clear_for_section` loses its only caller and goes to the dead-code list together with this cap.
**Resolution:** 🐞 BUG-907 (pattern `silent-result-cap`; the fix is in `app/dao/machine_section_assignment.py`) — decided by Claude under the reviewer's delegation (2026-10-16). Rules: `clear_for_section` R4. P3 was accepted too: `clear_for_section` is on the dead-code list "remove together with the fix of BUG-908"; BUG-907 stays logged until then and goes away with that removal (no separate fix needed if the removal comes first).

### P2. The two lookups also return assignments of deleted machines and to deleted sections — ✅ intended
**Background:** Machines and sections are soft-deleted (`is_deleted = True`, the row stays). Deleting a machine keeps its assignment row (machine DAO `soft_delete` R3). The reviewer decided for every DAO that raw lookups return deleted rows and the manager decides what to hide (base DAO spec, HR-4 scope; factory section DAO P2).
**What happens today:** `get_by_machine` returns the assignment of a soft-deleted machine, and an assignment pointing at a soft-deleted section; `get_by_section` returns the assignments of soft-deleted machines, and works the same for a soft-deleted section. Neither looks at the machine, section or factory row. Their only callers are this DAO's own write methods, which need exactly that (replace whatever row exists; remove every row of the section).
**Example:** Machine "Old Press" is deleted while assigned to "Cutting". "The assignment of Old Press" still returns the row; "the assignments of Cutting" still includes it. No user sees either list: the machines of a section shown to users come from the machine DAO, which hides deleted machines.
**Rules affected:** `get_by_machine` R2, `get_by_section` R2
**Answer:** intended — per base DAO precedent (HR-4 scope) and factory section DAO P2: raw lookups; hiding is the caller's decision.
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-16); rules unchanged. Rules: `get_by_machine` R2 ✅, `get_by_section` R2 ✅, `clear_for_section` R3 ✅.

### P3. Deleting a section permanently erases its machines' links — 🐞 BUG-908
**Background:** "Delete section" (`DELETE /factory-sections/{id}/`, `FactorySectionManager.delete_factory_section`) soft-deletes the section and then calls `MachineSectionAssignmentManager.clear_for_section`, which calls this DAO's `clear_for_section`: every assignment row of the section is **deleted** (a real DELETE, not a flag). The reviewer decided on 2026-10-11 that things belonging to a soft-deleted factory or section are hidden by the parent's state, their own rows untouched, so restoring the parent brings them back ("hidden, not cascaded"). The section DAO already follows it (`soft_delete` R3, `restore` R7 keep and return the assignments), and the machine DAO's "machines of a section" lookup will hide the machines of a deleted section (BUG-889). A "restore section" feature is to be built (section DAO FU-1).
**What happens today:** After "delete section" the machines of that section have no section at all. Restoring the section (section DAO `restore`) brings back an empty section: the links are gone and nothing records which machines were in it. (Verified: two machines assigned → delete section → no assignment rows left → restore → the section has no machines, each machine's section is empty.)
**Example:** "Paint" holds the machines "Sprayer 1" and "Sprayer 2". Someone deletes "Paint" by mistake; support restores it. "Paint" is back but empty, and each sprayer has to be reassigned by hand — if anyone remembers which ones they were.
**Rules affected:** none of this DAO — `clear_for_section` does what its name says (R1–R7). The change is in its caller: `FactorySectionManager.delete_factory_section` (`app/managers/factory_section_manager.py`) must stop calling `machine_section_assignment_manager.clear_for_section`. To be tagged in the section manager's spec; noted here in Follow-ups FU-1.
**Answer:** bug — per standing decision 2 ("hidden, not cascaded", 2026-10-11) and BUG-889 / BUG-891 precedent (`join-ignores-soft-deleted`: assignment rows are kept): deleting a section leaves its assignment rows untouched; its machines are hidden as members of the section while it is deleted (machine DAO BUG-889) and are in it again, unchanged, once it is restored. The fix is in `FactorySectionManager.delete_factory_section`, which must no longer call `MachineSectionAssignmentManager.clear_for_section`; that manager method and this DAO's `clear_for_section` (and `get_by_section`, used only by it) then have no caller and go to the dead-code list.
**Resolution:** 🐞 BUG-908 (pattern `soft-delete-cascades-hard-delete`; logged against `app/managers/factory_section_manager.py`, fix there) — decided by Claude under the reviewer's delegation (2026-10-16). The assignment manager spec and the section manager spec cite it. No rule of this DAO changes: `clear_for_section` (R1–R8) and `get_by_section` (R1–R7) are reachable today and stay specified and tested as they behave today. Added to `docs/testing/dead-code-removal-checklist.md` as "remove together with the fix of BUG-908": this DAO's `clear_for_section` and `get_by_section`, and `MachineSectionAssignmentManager.clear_for_section`.

### New questions

### Q1. The comment says loaded machines are refreshed; they are not — ✅ intended
**Background:** A machine reads its section through its assignment row (`machine.factory_section_id` is a read-only shortcut). SQLAlchemy keeps a machine that was already read in memory for the rest of the request. The comment on `clear_for_section` says it deletes rows one by one "so any already-loaded `Machine.section_assignment` … gets properly invalidated".
**What happens today:** It does not. A machine whose assignment was already read still reports the old section after `clear_for_section` — and after `upsert_for_machine` — until the caller expires or reloads it (verified). Both callers do expire it (`MachineSectionAssignmentManager.clear_for_section`, and `MachineManager.create_machine` / `update_machine` after setting the section), so no response shows a stale section today.
**Example:** A developer adds a new caller of `clear_for_section`, trusts the comment and returns the machine in the response: it shows "section: Paint" although the link was just removed.
**Rules affected:** `upsert_for_machine` R10, `clear_for_section` R6
**Suggested answer:** `intended` — the DAO only writes rows; refreshing objects already in memory is the caller's job, and both callers do it. The comment is wrong and should be corrected when the file is next touched (not a bug, no ID). Answer `bug — the DAO expires the machine's section_assignment itself` if every caller should be able to rely on it.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-16): the suggested answer is accepted; the comment is to be corrected when the file is next touched; no bug, no ID. Rules: `upsert_for_machine` R10 ✅, `clear_for_section` R6 ✅.

### Q2. Moving a machine to another section replaces its link instead of changing it — ✅ intended
**Background:** The assignment row has `created_at` / `created_by` and also `updated_at` / `updated_by` columns. `upsert_for_machine` never updates a row: it deletes the machine's row and inserts a new one.
**What happens today:** After moving a machine from "Cutting" to "Paint" its link is a new row (new `id`), `created_by` / `created_at` say who moved it and when, and nothing remembers who first put it into a section. `updated_at` / `updated_by` are never filled by this DAO (no code fills them). No API response shows any of these fields today.
**Example:** Rahim assigns "Press 4" to "Cutting" in January; Karim moves it to "Paint" in March. The link row reads "created by Karim, March"; "updated by" is empty.
**Rules affected:** `upsert_for_machine` R2, R4
**Suggested answer:** `intended` — the row means "this machine is in this section, put there by X at Y"; there is no history of earlier sections, and `updated_*` stay empty. Answer `bug — a move updates the row in place (factory_section_id, updated_by = the user, updated_at by the database) and keeps created_*` if the first assignment should be kept; then R2 / R4 change and BUG-909's intended behavior stays as it is.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-16): the suggested answer is accepted; rules unchanged. Rules: `upsert_for_machine` R2 ✅, R4 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here except where an ID is given. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Factory section manager** (`app/managers/factory_section_manager.py`, `delete_factory_section`) | BUG-908: must stop calling `machine_section_assignment_manager.clear_for_section` (P3). Its spec tags the "delete keeps the section's assignments" rule with BUG-908. Same follow-up as factory section DAO FU-2 (a). | P3 |
| FU-2 | **Machine section assignment manager** (`app/managers/machine_section_assignment_manager.py`) | (a) `clear_for_section` (manager) has `delete_factory_section` as its only caller; after BUG-908 it is unused → dead-code list together with this DAO's `clear_for_section` / `get_by_section`. Until then its behaviour (returns this DAO's ids; expires `section_assignment` of each machine it finds with `session.get`) inherits P1 / BUG-907 and BUG-906. (b) `set_assignment` validates the section (404 missing / other workspace via the raw section lookup, 400 "Cannot assign a machine to a deleted factory section", 400 "Factory section does not belong to this machine's factory") and then relies on `upsert_for_machine` — which checks nothing (R6, R7). It does **not** check the machine (workspace, deleted) or whether the section's **factory** is soft-deleted (standing decision 2 / BUG-904: a section of a deleted factory is hidden; assigning to it should probably be refused like a deleted section). (c) Whether a no-op `set_assignment` (same section) is a no-op follows from BUG-909 here. (d) Q1: it expires the machine itself — keep that. | P1, P3, Q1, BUG-909 |
| FU-3 | **Machine manager** (`app/managers/machine_manager.py`, `update_machine`) | Changing a machine's `factory_id` without sending `factory_section_id` keeps its assignment to a section of the **old** factory (nothing here or in the assignment manager clears it). Every edit that sends `factory_section_id` re-stamps the link (BUG-909 here). | `upsert_for_machine` R6, HR-9 line |
| FU-4 | **Machine DAO** (APPROVED) | No change asked. BUG-889 ("machines of a deleted section are hidden, assignment rows kept") becomes the normal path once BUG-908 is fixed, not only "left-over rows beyond 10 000". | P3 |

## Overview
`DAOMachineSectionAssignment` reads and writes rows of `machine_section_assignments` — the optional link that puts a machine into one section of its factory ("Press 4 is in Cutting"). Absence of a row means "unassigned". It serves `MachineSectionAssignmentManager`: `upsert_for_machine` for setting / changing / clearing a machine's section (reached from machine create and machine update), and `clear_for_section` for removing every link of a section (reached only from "delete section", which P3 questions). `get_by_machine` and `get_by_section` are its own helpers. It is meant to protect workspace isolation (every query filters by `workspace_id`) and "at most one section per machine" (also enforced by a unique index). It validates nothing about the machine, the section or the factory — the manager does. It never commits; writes are flushed.

**Callables:** 4 specified (+ 1 section on inherited `BaseDAO` behavior specific to this model) · 1 not specified
**Externals to mock:** none (no clock is read; `created_at` is set by the database)
**Integration-only behavior:** none.

**Model facts (table `machine_section_assignments`, class `app.models.machine_section_assignment.MachineSectionAssignment`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE (`machine_section_assignments_workspace_id_fkey`) | — |
| `machine_id` | Integer NOT NULL, FK `machines.id` ON DELETE CASCADE (`machine_section_assignments_machine_id_fkey`); **unique** (`uq_machine_section_assignment_machine`) | — |
| `factory_section_id` | Integer NOT NULL, FK `factory_sections.id` ON DELETE CASCADE (`machine_section_assignments_factory_section_id_fkey`) | — |
| `created_at` | DateTime NOT NULL | `now()` (database default — the **transaction start time**, so two rows written in one transaction have the same `created_at`) |
| `created_by` | Integer nullable, FK `profiles.id` (`machine_section_assignments_created_by_fkey`) | `NULL` |
| `updated_at` | DateTime nullable | `NULL`; set to `now()` on an ORM UPDATE |
| `updated_by` | Integer nullable, FK `profiles.id` (`machine_section_assignments_updated_by_fkey`) | `NULL` |

- **No soft-delete column**: unassigning deletes the row. Indexes: primary key, unique on `machine_id`, plain on `workspace_id`, `machine_id`, `factory_section_id`. No triggers.
- Nothing in the database ties the row's `workspace_id` to the machine's or the section's workspace, or the section's factory to the machine's factory.
- `Machine.section_assignment` (`uselist=False`, back-populates `MachineSectionAssignment.machine`); `machine.factory_section_id` / `machine.factory_section_name` are read-only properties reading it. `FactorySection` gets a backref `machine_assignments` (no cascade options; nothing uses it).
- Schema `MachineSectionAssignmentCreate` = `machine_id: int`, `factory_section_id: int` — no `workspace_id`; it is also the DAO's update schema. No validators.
- `Machine`: NOT NULL `workspace_id`, `name`, `factory_id`; `is_active`, `is_deleted` (default `False`), `is_running`. `FactorySection`: NOT NULL `workspace_id`, `name`, `factory_id`; `is_deleted` (default `False`). `Factory`: NOT NULL `workspace_id`, `name`, `abbreviation`.

**Cross-spec notes (not rules of this DAO):**
- The machine DAO's `get_by_section` (machines of a section, shown to users and used by work-order generation) joins this table; it hides soft-deleted machines and will hide machines of a deleted section (BUG-889) and of a deleted factory (BUG-891).
- "Delete section" = section DAO `soft_delete` **followed by** this DAO's `clear_for_section` through the assignment manager (P3 / BUG-908).
- No legacy test calls this DAO; tests elsewhere build assignment rows directly.

**Notes for the test designer:**
- Use the module singleton `machine_section_assignment_dao` (`from app.dao.machine_section_assignment import machine_section_assignment_dao`). Every parameter after `db` is keyword-only in all four methods (a positional call raises `TypeError`).
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `FactorySection`, `Machine` and `MachineSectionAssignment` rows directly (add + flush) with the NOT NULL columns above. The session runs with `autoflush=False`: flush before calling the DAO. For the 10 001-row case use a bulk `insert(...)` of machines (with `is_active=True, is_deleted=False, is_running=False`) and of assignment rows; it runs in a few seconds.
- **"Re-created" is observed through `id` and `created_by`, never `created_at`:** `created_at` is the transaction start time, identical for every row written in one test.
- **Looking at rows:** after a DAO write, check the table with a fresh `SELECT` (e.g. rows where `machine_id == M.id`), not through `machine.section_assignment` — that relationship is cached (R10 / Q1). Where a rule is *about* the cached relationship (`upsert_for_machine` R10, `clear_for_section` R6), read `machine.factory_section_id` once before the call so it is loaded.
- **Row order is unspecified today (BUG-906 `get_by_section` R6; BUG-100 inherited R3).** No `ORDER BY` is requested and the physical order on the test database is **not** deterministic. Write the order case to the intended order (`id` ascending, consecutive windows partition the rows) and mark it **non-strict** xfail (`strict=False`); never weaken the assertion. Every other case compares results as **sets** of ids / machine ids, or counts.
- **The 10 000 cap (BUG-907, `clear_for_section` R4):** 10 001 rows → intended: all 10 001 machine ids returned and 0 rows left; today 10 000 and 1 → deterministic as counts → **strict** xfail.
- **Same section re-saved (BUG-909, `upsert_for_machine` R3):** today the row id changes and `created_by` becomes the second user → deterministic → **strict** xfail. Use two different profiles for the first and the second save.
- **Database errors** (unique, foreign key, negative `limit` / `skip`): wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`; after the savepoint is rolled back the machine's previous row is back (R8).
- **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, then re-select.

## Not specified
- `machine_section_assignment_dao` — module-level singleton `DAOMachineSectionAssignment(MachineSectionAssignment)`, no logic
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — not overridden; specified in `tests/unit/dao/base.spec.md`. None of them has a caller on this DAO; only what is specific to this model is stated below ("Inherited `BaseDAO` methods on `MachineSectionAssignment`").

All four methods are reached today (`upsert_for_machine` from machine create / update; `clear_for_section` from delete section; the two lookups from those), so all are specified and tested as they behave today. The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks none as possibly unused. P3 was accepted (2026-10-16, decided by Claude under the reviewer's delegation): `clear_for_section` and `get_by_section` lose their only caller once BUG-908 is fixed and are on `docs/testing/dead-code-removal-checklist.md` as "remove together with the fix of BUG-908" (with `MachineSectionAssignmentManager.clear_for_section`); their tests are deleted in the same change. The `skip` parameter and the `limit=500` default of `get_by_section` are never used by any caller (its only caller passes `limit=10000`); they are specified because the method is public.

---

## `DAOMachineSectionAssignment.get_by_machine(db, *, machine_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** internal (used by: `upsert_for_machine`; no other caller in `app/` or `tests/`)

**Purpose:** The assignment row of one machine in a workspace, if it has one.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | equality on `machine_id`; not validated |
| `workspace_id` | int | equality on the assignment row's own `workspace_id` (not the machine's) |

**Returns:** the `MachineSectionAssignment` instance, or `None`.

**Rules:**
- **R1.** Given a machine with an assignment row in the workspace, that row is returned. Given a machine without one, an unknown machine id, or a `workspace_id` other than the row's own, `None` is returned (a row of another workspace is never returned).
- **R2.** ✅ (P2) The machine, section and factory rows are not looked at: the row is returned when the machine is soft-deleted, when the section it points at is soft-deleted, and when the section belongs to another factory or workspace than the machine.
- **R3.** Nothing is written.

**Errors:** none.

**Side effects:** none

---

## `DAOMachineSectionAssignment.get_by_section(db, *, factory_section_id, workspace_id, skip=0, limit=500)`
**Shape:** list
**Persistence:** reads
**Visibility:** internal (used by: `clear_for_section` with `limit=10000`; no other caller in `app/` or `tests/`)

**Purpose:** One page of the assignment rows that point at a section.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `factory_section_id` | int | equality on `factory_section_id`; not validated |
| `workspace_id` | int | equality on the assignment row's own `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated; no caller passes it |
| `limit` | int, default `500` | max rows; not validated |

**Returns:** a `list` of `MachineSectionAssignment` instances (possibly empty).

**Rules:**
- **R1.** Only rows with `factory_section_id` and `workspace_id` equal to the arguments are returned. A row of the same section id with another `workspace_id`, and rows pointing at other sections, are never returned.
- **R2.** ✅ (P2) The machine and section rows are not looked at: rows of soft-deleted machines are returned, and the rows of a soft-deleted section are returned exactly as for a live one.
- **R3.** An unknown section id, or a section with no rows in the workspace, returns `[]`.
- **R4.** Filters are applied before `skip` / `limit`. With defaults at most 500 rows are returned — given 501 rows of the section, exactly 500; with `limit=501`, 501.
- **R5.** `limit=0` returns `[]`; `skip` at or past the number of matching rows returns `[]`. A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R6.** [BUG-906] (HR-6) Rows are ordered by `id` ascending before `skip` / `limit`, so consecutive windows (`skip=0, limit=2`, `skip=2, limit=2`, …) partition the section's rows with no repeats or gaps. *(Today: no ordering is requested; the order is whatever the database produces and is not specified.)*
- **R7.** Nothing is written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `DAOMachineSectionAssignment.upsert_for_machine(db, *, machine_id, factory_section_id, workspace_id, user_id)`
**Shape:** create / delete (replace)
**Persistence:** writes
**Visibility:** public (used by: `MachineSectionAssignmentManager.set_assignment` ← `MachineManager.create_machine` when `factory_section_id` is given, and `MachineManager.update_machine` whenever `factory_section_id` is in the request (including `null`) ← `POST /machines/`, `PUT /machines/{id}/`. The manager first refuses a missing / other-workspace section (404), a deleted section (400) and a section of another factory (400); it checks nothing about the machine.)

**Purpose:** Put a machine into a section, move it to another one, or clear its section.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | machine to (re)assign; must reference an existing machine (FK) — nothing else checked (workspace, deleted, factory) |
| `factory_section_id` | int \| `None` | `None` = clear; otherwise must reference an existing section (FK) — nothing else checked (workspace, factory, deleted) |
| `workspace_id` | int | stored on the new row and used to find the machine's existing row; must reference an existing workspace (FK) |
| `user_id` | int | stored in `created_by`; must reference an existing profile (FK); `None` is stored as `NULL` |

**Returns:** the new `MachineSectionAssignment` (flushed, not committed), or `None` when `factory_section_id` is `None`.

**Rules:**
- **R1.** Given a machine without an assignment and a section id, one row is created with `workspace_id`, `machine_id`, `factory_section_id` as given, `created_by = user_id`, `created_at` set by the database, `updated_at = None`, `updated_by = None`; it is returned and is the machine's only row.
- **R2.** ✅ (Q2) Given a machine assigned to section A and a different section B, afterwards the machine has exactly one row, pointing at B; it is a new row (different `id`) with `created_by = user_id`; the old row is gone. `updated_at` / `updated_by` stay `None`.
- **R3.** [BUG-909] (HR-9) Given a machine already assigned to exactly the section passed, nothing is written: the existing row is returned with the same `id`, `created_by` and `created_at`. *(Today: the row is deleted and a new one inserted — new `id`, `created_by` = the given user; still exactly one row.)*
- **R4.** ✅ (Q2) Given `factory_section_id=None` and a machine with an assignment, the row is deleted and `None` is returned; the machine has no row afterwards. Given `None` and a machine without an assignment, `None` is returned and nothing is written. `user_id` is not used in either case.
- **R5.** Only the machine's own row is touched: rows of other machines (in the same section or not) are unchanged. The machine, section and factory rows are never written.
- **R6.** Nothing about the target is checked: the row is created for a section of another factory than the machine's, a soft-deleted section, a section of another workspace, a soft-deleted machine, and a machine of another workspace (stored with the given `workspace_id`). (The manager refuses the first three before calling; the others are not refused anywhere — FU-2.)
- **R7.** The existing row is looked for only in the given workspace (`get_by_machine` R1). Given a machine whose row has another `workspace_id`, that row is not found and not deleted; the insert then violates the one-row-per-machine constraint (see Errors) and nothing changes.
- **R8.** Given a `machine_id`, `factory_section_id`, `user_id` or `workspace_id` that references no row, the flush fails (see Errors). Inside a savepoint that is rolled back, the machine's previous row (if any) is back unchanged.
- **R9.** Changes are flushed, not committed: in the same session `get_by_machine` returns the new row (or `None` after clearing); rolling back restores the previous state.
- **R10.** ✅ (Q1) A `Machine` object whose `section_assignment` was already loaded in the session is not refreshed: its `factory_section_id` still gives the old section (or the old value after clearing) until the machine is expired or reloaded; then it gives the new value. A later flush of that machine (e.g. after changing its name) does not bring the deleted row back.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| the machine's existing row has another `workspace_id` (R7) | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.UniqueViolation` (constraint `uq_machine_section_assignment_machine`) | — (not asserted) |
| unknown `machine_id` | `IntegrityError` / `ForeignKeyViolation` (`machine_section_assignments_machine_id_fkey`) | — |
| unknown `factory_section_id` | `IntegrityError` / `ForeignKeyViolation` (`machine_section_assignments_factory_section_id_fkey`) | — |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` (`machine_section_assignments_created_by_fkey`) | — |
| unknown `workspace_id` | `IntegrityError` / `ForeignKeyViolation` (`machine_section_assignments_workspace_id_fkey`) | — |

**Side effects:** at most one `machine_section_assignments` row deleted and at most one inserted, flushed; no commit; no other table written.

---

## `DAOMachineSectionAssignment.clear_for_section(db, *, factory_section_id, workspace_id)`
**Shape:** delete (bulk)
**Persistence:** writes
**Visibility:** public (used by: `MachineSectionAssignmentManager.clear_for_section` ← `FactorySectionManager.delete_factory_section` ← `DELETE /factory-sections/{id}/`, right after the section is soft-deleted — questioned in P3 / BUG-908)

**Purpose:** Unassign every machine of a section and say which machines they were.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `factory_section_id` | int | section whose rows are removed; not validated (any integer) |
| `workspace_id` | int | only rows with this `workspace_id` are removed |

**Returns:** a `list` of the `machine_id`s of the removed rows (each once), possibly empty. Order: see R7.

**Rules:**
- **R1.** Every assignment row with this `factory_section_id` and `workspace_id` is deleted (a real DELETE) and its `machine_id` is in the returned list; the list has one entry per deleted row.
- **R2.** Rows pointing at other sections, and rows of other workspaces pointing at the same section id, are not touched and their machines are not in the list.
- **R3.** ✅ (P2) The state of the section and of the machines does not matter: rows of soft-deleted machines are deleted and listed too; the call works the same whether the section is live or soft-deleted. The section, machine and factory rows themselves are never written.
- **R4.** [BUG-907] (P1) All matching rows are deleted however many there are: given 10 001 rows, 10 001 machine ids are returned and no row is left. *(Today: at most 10 000 rows are handled — 10 001 rows → 10 000 ids, 1 row left, which one is not specified; a second call removes it.)*
- **R5.** An unknown section id, or a section with no rows in the workspace, returns `[]` and writes nothing.
- **R6.** ✅ (Q1) A `Machine` whose `section_assignment` was already loaded still reports the removed section until it is expired or reloaded; then it reports `None`. (Contrary to the method's comment.)
- **R7.** [BUG-906] The returned ids follow the order of `get_by_section` R6 (row `id` ascending). *(Today: unspecified.)* Tests compare the list as a set except in the order case.
- **R8.** Changes are flushed, not committed: in the same session `get_by_section` returns `[]`; rolling back a savepoint around the call brings every row back.

**Errors:** none raised by the method itself (no foreign key points at the assignment table).

**Side effects:** up to 10 000 (intended: all) `machine_section_assignments` rows deleted and flushed; no commit; no other table written.

---

## Inherited `BaseDAO` methods on `MachineSectionAssignment`
**Shape:** create / update / get / list
**Persistence:** writes / reads
**Visibility:** public, but **no caller** on this DAO in `app/` or `tests/`

**Purpose:** `DAOMachineSectionAssignment` overrides none of the generic methods; the base spec (`tests/unit/dao/base.spec.md`) applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a `MachineSectionAssignmentCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and nothing is saved. `create` with a dict holding `workspace_id`, `machine_id`, `factory_section_id` creates a row with `created_at` set by the database and `created_by`, `updated_at`, `updated_by` `None`; a second row for the same machine raises `IntegrityError` (`UniqueViolation`, `uq_machine_section_assignment_machine`).
- **R2.** `update` with a dict sets the given columns (e.g. `{"factory_section_id": B, "updated_by": U}`); `updated_at` becomes non-null (base spec `update`).
- **R3.** [BUG-100] (HR-6) `get_by_workspace` returns the workspace's rows ordered by `id` ascending before `skip` / `limit` (base spec `get_by_workspace` R3). *(Today: no ordering is requested.)* `get` and `get_multi` have no workspace filter (base spec).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `create` with the schema (no `workspace_id`) | `IntegrityError` / `NotNullViolation` | — |
| `create` of a second row for a machine | `IntegrityError` / `UniqueViolation` | — |

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 17 | keyword-only parameters | Notes for the test designer |
| 19–22 | `machine_id` + `workspace_id` filter; `.first()` → row / `None` (own / other workspace / none); no join to machine, section or factory | `get_by_machine` R1, R2, R3 |
| 26 | defaults `skip=0`, `limit=500` | `get_by_section` R4 |
| 30–33 | `factory_section_id` + `workspace_id` filter; no join (deleted machines / section) | `get_by_section` R1, R2, R3 |
| 34 | offset / limit, no `ORDER BY` (BUG-906); `limit=0`; negative values; empty / one / many | `get_by_section` R4, R5, R6, R7, Errors |
| 43 | existing row looked up in the given workspace only | `upsert_for_machine` R7 |
| 44–46 | `if existing:` → delete + flush (also when the section is the same — BUG-909) / no existing row | `upsert_for_machine` R2, R3, R4, R5, R10 |
| 47–48 | `if factory_section_id is None:` → return `None` (with / without previous row) | `upsert_for_machine` R4 |
| 49–55 | insert with `created_by`; no validation of machine / section / factory / workspace; FK and unique errors at flush; return new row, no commit | `upsert_for_machine` R1, R2, R6, R7, R8, R9, Errors |
| 64 | `get_by_section(..., limit=10000)` — cap (BUG-907), order (BUG-906) | `clear_for_section` R4, R7 |
| 65 | list of `machine_id`s (empty / one / many) | `clear_for_section` R1, R5 |
| 66–67 | `for row in rows: db.delete(row)` — zero / one / many; no state check; loaded machines not refreshed | `clear_for_section` R1, R2, R3, R5, R6 |
| 68–69 | flush, return ids, no commit | `clear_for_section` R8 |
| 72 | module singleton | Not specified |
| `base.py` 76–84 | `create`: schema lacks `workspace_id`; dict; unique on `machine_id` | inherited R1 |
| `base.py` 108–119 | `update` with dict | inherited R2 |
| `base.py` 161–167 | `get_by_workspace` no `ORDER BY` (BUG-100) | inherited R3 |
