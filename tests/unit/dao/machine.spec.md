# Spec — `app/dao/machine.py`

> **Status:** APPROVED (2026-10-11: Q8 and Q9 accepted as suggested; nothing provisional remains)
> **Source commit:** e48a092

> **Review round 2026-10-11 (2).** The reviewer answered `ok`: Q8 and Q9 are `intended` for the DAO, and the "hidden, never deleted or altered" reading of P1 / P2 below was put to the reviewer explicitly, with the alternative, and confirmed. Nothing is open.
>
> **Standing reviewer decision applied (2026-10-10, inventory DAO Q2):** "Soft-deleted things should not show up. We keep the information, but it is not used for anything counted." It is applied here to machines whose **factory** or **section** is soft-deleted (P1, P2, HR-4 line).
>
> **Review round 2026-10-10 (1).** The reviewer's words, verbatim: *"if factories can be soft delted, then these should be soft deleted but stays hidden cause we need to be bable to put them back if user undos. yea these ones that are inteded at dao q2 and q3 makes sense but keep note thta they need to be look at at endpoint and schema, keep restore, remove"*.
> How that was read (**main session's interpretation**, not the reviewer's own wording — correct any line that is wrong):
> - **P1, P2 → confirmed as bugs** (BUG-890, BUG-891), with the reason now explicit: machines of a soft-deleted factory are **hidden, never deleted or altered**, so that restoring the factory brings them back exactly as they were.
> - **Q2, Q3 → confirmed intended at the DAO**, with a follow-up each: Q2 in the machines **endpoint** review, Q3 in the **schema / manager** review (see **Follow-ups for other reviews**).
> - **Q5 → changed: keep `restore`.** It is specified in full below and taken off the dead-code list.
> - **Q4, Q6 → confirmed `remove`.**
> - P3, Q1, Q7 were not mentioned in that sentence; see round (2).
>
> **Review round 2026-10-10 (2)** (relayed by the main session): the main session restated the remaining answers to the reviewer — **P3** (untrimmed search is a bug; trim, tabs and newlines included), **Q1** (the latest-status crash is a bug; latest = newest `created_at`, ties to the highest `id`), **Q7** (intended) — and the reviewer replied *"yuyp"*. All three are confirmed as suggested. For P3, "whitespace" means what Python's `str.strip()` removes: spaces, tabs and newlines.
>
> **Revision 2026-10-10 (1) — what changed, for the case designer:**
> - **New callable section:** `restore` R1, R2, R2a, R3, R4, R5, R6, R7, R7a, R8, R9 (all new; R7a is tagged [BUG-890] / [BUG-891]; R2a and R9 rest on Q8, Q9, accepted 2026-10-11).
> - **New rules:** `get_by_factory` R3b · `get_by_section` R3b · `search_advanced` R3c (a machine is visible again, unchanged, once its factory is no longer deleted; hold today and after the fix).
> - **Changed rules:** `get_by_factory` R3a and `get_by_section` R3a (narrowed to the broken part only — "hidden"; the parts that already hold moved to the new R3b, which also closes cases-file gap 1) · `search_advanced` R3a (wording: hidden by the factory's state alone; behavior and example unchanged) · `soft_delete` R5 (one sentence added: `restore` undoes it).
> - **Changed (clarified):** `search_advanced` R8 — "whitespace" now defined as spaces, tabs and newlines (`str.strip()`), for both the trim and the whitespace-only case (closes cases-file gap 2).
> - **Tag only, behavior unchanged:** the "(pilot default — awaiting reviewer)" marker was removed from `search_advanced` R8 (P3), R10, R11 (Q3), R12 (Q1), R13, R15 (Q2), from the R3a rules (P1, P2) and from inherited R2, R4 (Q7).
> - **Not specified:** `restore` left the list (now specified); `get_active_by_workspace` and the `include_deleted` parameter are now reviewer-confirmed dead code.
> - Notes for the test designer: two new bullets (**Factory no longer deleted**, **Restore**). Branch map: rows 31–34, 44–49 and 110–113 now also point at the new R3b / R3c; row 80–90 replaced by rows 84–87 and 88–90.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Short list — still open; answer here if you agree with the suggestions
| # | In one line | Answer (accepted) |
|---|---|---|
| Q8 | *(new)* Restoring a machine records nobody and writes no activity entry | intended for the DAO (the future "restore machine" feature must record it) |
| Q9 | *(new)* Restoring a machine can bring back a name that another machine of the same factory now uses | intended for the DAO (the future "restore machine" feature must refuse it) |

### Decided — nothing to do
| # | In one line | Decision |
|---|---|---|
| HR lines | 4 house-rule violations (sort order ×2, search wildcards, deleted section) | stand as written (BUG-887, BUG-343, BUG-888, BUG-889) |
| P1 | Machines of a deleted factory still appear on the machines page | bug — hidden, never deleted or altered (BUG-890) — reviewer, 2026-10-10 |
| P2 | Machines of a deleted factory still get work-order drafts / are returned by the factory and section lookups | bug — hidden, never deleted or altered (BUG-891) — reviewer, 2026-10-10 |
| Q2 | Unknown sort field / sort direction is silently replaced by "name, ascending" | intended at the DAO; to be looked at in the machines endpoint review — reviewer, 2026-10-10 |
| Q3 | A model number / manufacturer of only spaces counts as "has a value" | intended at the DAO; to be looked at in the schema / manager review — reviewer, 2026-10-10 |
| Q4 | "All live machines of the workspace" method is never called | remove — reviewer, 2026-10-10 |
| Q5 | "Restore a deleted machine" method is never called | **keep** — specified below — reviewer, 2026-10-10 |
| Q6 | "Include deleted machines" option on the factory / section lookups is never used | remove — reviewer, 2026-10-10 |
| P3 | Search text is not trimmed; a search of only spaces returns (almost) nothing | bug — trim (spaces, tabs, newlines); whitespace-only = no search (BUG-892) — reviewer, 2026-10-10 (2) |
| Q1 | Filtering the machines page by latest status always crashes (500) | bug — make it work; latest = newest `created_at`, ties to highest `id` (BUG-886) — reviewer, 2026-10-10 (2) |
| Q7 | Handing the create/update form straight to the DAO crashes | intended (callers pass a prepared dict) — reviewer, 2026-10-10 (2) |

### House-rule violations — applied automatically

- **HR-6** `search_advanced` R14 — sorting by name uses the database's default text ordering: on a case-only tie ("Bolt" / "bolt") the collation decides, not the `id`. Intended: name case-insensitive, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-887 (pattern `unordered-pagination`). Rules: `search_advanced` R14.
- **HR-6** `get_by_factory` R6, `get_by_section` R7 — no sort order at all; paging with `skip`/`limit` can repeat or skip machines. Intended: name case-insensitive ascending, then `id` ascending, before `skip`/`limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-343 (existing, logged against `app/utils/work_order_generation.py` and naming these two DAO methods; the fix is here) — no new ID. Rules: `get_by_factory` R6, `get_by_section` R7.
- **HR-8** `search_advanced` R9 — the search text is put into `ILIKE '%…%'` unescaped: `%` or `_` alone matches every machine, `\` acts as an escape character. Intended: `%`, `_` and `\` match literally in name, model number and manufacturer.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** 🐞 BUG-888 (pattern `unescaped-like-wildcards`). Rules: `search_advanced` R9.
- **HR-4** (third bullet: filters through related rows ignore soft-deleted related rows) `get_by_section` R4, `search_advanced` R6a — a section filter naming a soft-deleted section still returns the machines assigned to it. Intended: a soft-deleted section matches no machine. (Deleting a section normally removes its assignments, so this only shows with left-over assignment rows — e.g. more than 10 000 assignments, or rows written directly.)
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-889 (pattern `join-ignores-soft-deleted`). Rules: `get_by_section` R4, `search_advanced` R6a.

### Precedent matches — all confirmed by the reviewer

### P1. Machines of a deleted factory still appear on the machines page — 🐞 BUG-890
**Background:** Factories are soft-deleted (`is_deleted = True`, row stays). Every machine belongs to exactly one factory. Deleting a factory does not touch its machines, and the machine list never looks at the factory row. The reviewer already ruled for stock (inventory DAO Q2, BUG-882): things inside a soft-deleted factory must not show up or be counted.
**What happens today:** Live machines of a soft-deleted factory are returned by `GET /machines/` — with no factory filter and when that factory's id is given.
**Example:** Factory 9 "Old Plant" is deleted while it still has machine "Press 4". The machines page still lists "Press 4" with factory id 9, although no factory "Old Plant" exists in the UI any more.
**Rules affected:** `search_advanced` R3a
**Answer:** bug — a machine whose factory is soft-deleted is hidden: not returned by the machine search (with or without a factory filter). It is hidden only because of the factory's state; the machine row is never deleted or changed, so that restoring the factory brings the machine back exactly as it was. An inactive-but-live factory still counts. (Reviewer, 2026-10-10: "these should be soft deleted but stays hidden cause we need to be bable to put them back if user undos" — read as a confirmation of the suggested answer plus its reason; **main session's interpretation**.)
**Resolution:** 🐞 BUG-890 (pattern `join-ignores-soft-deleted`; per BUG-882 precedent). Rules: `search_advanced` R3a (tagged), R3b and R3c (untagged — what already holds: nothing is altered, and the machine is visible again once the factory is no longer deleted).
- **Reading note (main session's interpretation):** "these should be soft deleted" is read as "these are affected by the factory's soft delete", not as "set `is_deleted = True` on each machine when the factory is deleted". Marking the machines themselves deleted would make "put them back" impossible to do exactly: on undo, a machine the user had deleted on purpose before the factory was deleted could not be told apart from one deleted along with the factory. If the reviewer did mean a cascading soft delete, overwrite this answer — R3a–R3c of the three list methods and `restore` R7 / R7a would then be rewritten.
- **Follow-up for the factory review:** nothing in the application restores a factory today (`DAOFactory.restore` exists and has no caller; there is no restore endpoint, service or manager method). The "undo" the reviewer describes therefore has no entry point yet — recorded under **Follow-ups for other reviews**.

### P2. Machines of a deleted factory are still returned by the factory and section lookups — 🐞 BUG-891
**Background:** "Machines of one factory" and "machines of one section" are used when work orders are generated from a template (one draft per machine) and, for the factory lookup, by the duplicate-name check when a machine is created or renamed. Neither looks at the factory row.
**What happens today:** Live machines of a soft-deleted factory are returned.
**Example:** A weekly template is run for Factory 9, which was deleted last month. Drafts are still created for its 12 machines.
**Rules affected:** `get_by_factory` R3a, `get_by_section` R3a
**Answer:** bug — a machine whose factory is soft-deleted is hidden: not returned by `get_by_factory` or `get_by_section`. Hidden by the factory's state only; the machine rows and their section assignments are never deleted or changed, so that restoring the factory brings them back exactly as they were. (Reviewer, 2026-10-10, same sentence as P1; **main session's interpretation**.)
**Resolution:** 🐞 BUG-891 (pattern `join-ignores-soft-deleted`; per BUG-882 / BUG-884 precedent). Own ID (not an extension of BUG-890): different methods and a different API surface (work-order generation), so a separate fix and xfail reason — same split as BUG-882 / BUG-884. Rules: `get_by_factory` R3a, `get_by_section` R3a (tagged); `get_by_factory` R3b, `get_by_section` R3b (untagged — what already holds).

### P3. Search text is not trimmed; a search of only spaces returns almost nothing — 🐞 BUG-892
**Background:** The machines page has a free-text search over name, model number and manufacturer. The text is used exactly as typed, including leading / trailing spaces. An empty text means "no search". The stock page's search (inventory DAO) trims the text and treats only-spaces as "no search".
**What happens today:** `" bolt "` finds nothing although a machine "Bolt cutter" exists; a search of three spaces returns only machines whose name, model number or manufacturer contains three spaces in a row.
**Example:** A user pastes "Press 4 " (with a trailing space) into the search box and gets an empty list.
**Rules affected:** `search_advanced` R8
**Answer:** bug — per BUG-637 precedent (`whitespace-search-empties-results`): leading / trailing whitespace is removed before matching; a whitespace-only search applies no search filter; whitespace includes tabs and newlines (reviewer confirmed, 2026-10-10 round 2, as restated by the main session)
**Resolution:** 🐞 BUG-892 (pattern `whitespace-search-empties-results`). "Whitespace" = what Python's `str.strip()` removes (spaces, tabs, newlines). Rules: `search_advanced` R8.

### New questions

### Q1. Filtering the machines page by latest status always crashes — 🐞 BUG-886
**Background:** `GET /machines/?latest_event_type=RUNNING` (IDLE / RUNNING / OFF / MAINTENANCE) should return the machines whose most recent status change is that status. Status changes are rows of the machine activity log (`event_type = "status_updated"`, the status stored in the row's JSON `metadata` under `"status"`). The filter reads that JSON value with a Postgres-only accessor (`.astext`) that the column's declared type (generic `JSON`) does not have.
**What happens today:** Any call with `latest_event_type` set raises `AttributeError` while the query is being built — before the database is asked anything. Through the API this is a 500 for every status value, whatever data exists. Without the filter the list works.
**Example:** A user picks "Running" in the status filter of the machines page: the page fails with a server error, even though 5 machines are running.
**Rules affected:** `search_advanced` R12, R12a–R12e
**Suggested answer:** `bug — the filter returns the machines whose latest status change has that status; "latest" = newest created_at, ties broken by highest id (the same rule the machine page uses to show a machine's current status); a machine with no status change never matches; each machine appears once`
**Answer:** bug — as suggested (reviewer confirmed, 2026-10-10 round 2, as restated by the main session)
**Resolution:** 🐞 BUG-886 (pattern `wrong-dialect-json-accessor`). Rules: `search_advanced` R12 (tagged), R12a–R12e (tagged — the detailed intended behavior; all fail today for the same reason).

### Q2. An unknown sort field or sort direction is silently replaced by "name, ascending" — ✅ intended
**Background:** The list can be sorted by `name` or `created_at`, ascending or descending. `GET /machines/` accepts any text for `sort_by` and `sort_dir`. (`maintenance_date` is a third sort field handled by the manager, not by this DAO.)
**What happens today:** Any `sort_by` other than exactly `"name"` / `"created_at"` sorts by name. Any `sort_dir` other than exactly lower-case `"desc"` sorts ascending — including `"DESC"` and `"descending"`.
**Example:** `GET /machines/?sort_by=createdAt&sort_dir=DESC` returns the machines A→Z by name with no error; the caller believes they are newest-first.
**Rules affected:** `search_advanced` R13, R15
**Suggested answer:** `intended` for this DAO — a lenient fallback is harmless at this level. Rejecting unknown values (422) is the endpoint's job and should be raised when the machine manager / endpoint is reviewed; no bug is logged here.
**Answer:** intended at the DAO — to be looked at in the machines endpoint review (reviewer, 2026-10-10: "these ones that are inteded at dao q2 and q3 makes sense but keep note thta they need to be look at at endpoint and schema")
**Resolution:** rules unchanged. Rules: `search_advanced` R13 ✅, R15 ✅. No bug is logged against this DAO. **Follow-up FU-1** (machines endpoint review) — see **Follow-ups for other reviews**.

### Q3. A model number or manufacturer made only of spaces counts as "has a value" — ✅ intended
**Background:** The machines page can filter on "has a model number" / "has a manufacturer" (yes / no). "No" means empty: not set, or the empty text `""`. The create / update forms do not trim these two fields.
**What happens today:** A machine whose model number is `"   "` is listed under "has a model number: yes" and not under "no".
**Example:** A user clears the model number by typing a space. The machine still shows up when filtering for machines that have a model number.
**Rules affected:** `search_advanced` R10, R11
**Suggested answer:** `intended` for this DAO — the filter is right to compare what is stored; the fix is to trim these fields when they are saved (form schema, HR-1 style), to be decided in the machine manager review.
**Answer:** intended at the DAO — to be looked at in the schema / manager review (reviewer, 2026-10-10, same sentence as Q2)
**Resolution:** rules unchanged. Rules: `search_advanced` R10 ✅, R11 ✅. No bug is logged against this DAO. **Follow-up FU-2** (machine schema / manager review) — see **Follow-ups for other reviews**.

### Q4. "All live machines of the workspace" is never called — 🗑️ remove
**Background:** `DAOMachine.get_active_by_workspace` returns the non-deleted machines of a workspace, unordered, paged. The machines page uses `search_advanced` instead.
**What happens today:** Nothing in `app/` or `tests/` calls it (the only matches for the name are the definition itself and same-named methods of two other DAOs, `production_formula` and `production_line`).
**Example:** No API request, background job or script reaches it; breaking it has no visible effect.
**Rules affected:** `get_active_by_workspace` (all)
**Suggested answer:** `remove`
**Answer:** remove (reviewer, 2026-10-10; **main session's interpretation** of the closing "remove")
**Resolution:** not specified; listed under **Not specified** as dead code, to be removed (reviewer), and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/machine.py:54`). Not a bug — no BUG ID.

### Q5. "Restore a deleted machine" is never called — ✅ keep (reviewer: "keep restore")
**Background:** `DAOMachine.restore` brings a soft-deleted machine back (`is_deleted = False`, `is_active = True`, deletion stamp cleared). There is no "restore machine" endpoint, manager method or service method.
**What happens today:** Nothing in `app/` or `tests/` calls it. A deleted machine cannot be brought back through the application.
**Example:** A user deletes "Press 4" by mistake; there is no button or API call that restores it.
**Rules affected:** `restore` (all)
**Suggested answer:** `remove` — if un-deleting machines is wanted, it is a feature to build (endpoint + manager + audit event), and the method would be specified then. Answer `intended` instead if a restore feature is planned soon and the method should be kept and tested now.
**Answer:** intended — keep `restore` (reviewer, 2026-10-10: "keep restore"; this overrides the suggested `remove`)
**Resolution:** `restore` is **not** dead code: machines must be able to be put back. It is specified in full in its own section (`restore` R1–R9) and its entry was taken out of `docs/testing/dead-code-removal-checklist.md`. That nothing calls it today is a note, not a bug: the "restore machine" feature (endpoint + service + manager method) is still to be built — see **Follow-ups for other reviews** (FU-3). Specifying it raised two new questions, **Q8** and **Q9**, and no bug: the method does what its name says.

### Q6. The "include deleted machines" option of the factory and section lookups is never used — 🗑️ remove
**Background:** `get_by_factory` and `get_by_section` have an `include_deleted` option (default off) that would also return soft-deleted machines. Their callers — the duplicate-name check and work-order generation — never pass it.
**What happens today:** The option can never be on in production.
**Example:** Both callers always get live machines only.
**Rules affected:** `get_by_factory`, `get_by_section` (the `include_deleted` parameter only)
**Suggested answer:** `remove` (the parameter and its `if`; the methods stay and always exclude deleted machines)
**Answer:** remove — the parameter only (reviewer, 2026-10-10; **main session's interpretation** of the closing "remove")
**Resolution:** the parameter is not specified (the two methods stay specified); listed under **Not specified** as a dead parameter, to be removed (reviewer), and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/machine.py:28,35-36` and `:41,50-51`). Not a bug — no BUG ID.

### Q7. Handing the create / update form straight to the DAO crashes — ✅ intended
**Background:** The machine forms carry `factory_section_id`, but a machine's section is not a column of the machine: it lives in a separate assignment row, and `machine.factory_section_id` is a read-only shortcut. The generic "create" and "update" of the DAO copy every form field onto the machine. The manager knows this: it always passes a prepared dict without `factory_section_id` and sets the section through the assignment manager.
**What happens today:** `machine_dao.create(obj_in=MachineCreate(...))` always raises `AttributeError` (the form always carries the field, `None` by default); `machine_dao.update` raises the same error when given a dict or form in which `factory_section_id` is set to a value. Nothing is saved. No production code path does this.
**Example:** A developer writes a new import script that calls `machine_dao.create(db, obj_in=MachineCreate(name="Press", factory_id=1))` — it fails immediately instead of creating a machine without a section.
**Rules affected:** inherited methods R2, R4
**Suggested answer:** `intended` — the DAO is right not to accept a field it cannot store; the rules document the trap so it is tested and not silently changed.
**Answer:** intended (reviewer confirmed, 2026-10-10 round 2, as restated by the main session)
**Resolution:** rules unchanged. Rules: inherited methods R2 ✅, R4 ✅.

### New questions about `restore` (raised by the Q5 decision "keep restore")
> Both were accepted by the reviewer on 2026-10-11.

### Q8. Restoring a machine records nobody and writes no activity entry — ✅ intended
**Background:** Deleting a machine records who did it (`deleted_by`) and when, and the manager writes a "deactivated" entry in the machine's activity log. `restore` takes only the machine — it has no "who" argument. It clears the deletion stamp and writes nothing else.
**What happens today:** After a restore nothing shows that the machine was ever deleted or who brought it back: `deleted_at` / `deleted_by` are cleared, `updated_by` keeps its old value, and no activity entry is written.
**Example:** Rahim deletes "Press 4" on Monday, Karim restores it on Tuesday (once the feature exists). The machine row shows no trace of either action; the activity log shows Monday's "deactivated" entry and nothing for Tuesday.
**Rules affected:** `restore` R2a
**Suggested answer:** `intended` for this DAO — same as the already approved `InventoryDAO.restore` (inventory spec `restore` R2: "no user is stamped — the method has no user argument"). Recording who restored (`updated_by`, HR-9) and writing a "restored" activity entry is the job of the manager method that will call it; noted as follow-up FU-3. Answer `bug — restore takes the acting user and stamps updated_by` if the DAO itself should record it.
**Answer:** intended (reviewer, 2026-10-11)
**Resolution:** rule unchanged. Rules: `restore` R2a ✅.

### Q9. Restoring a machine can bring back a name that another machine of the same factory now uses — ✅ intended
**Background:** Machine names are unique per factory among live machines; the check is made by the manager when a machine is created or renamed, and a deleted machine's name can be reused (HR-2). There is no database constraint on machine names. `restore` checks nothing.
**What happens today:** Restoring a deleted machine whose name was reused in the meantime succeeds, and the factory then has two live machines with the same name.
**Example:** "Press 4" is deleted; a new machine "Press 4" is created in the same factory; the old one is restored. The machines page now lists "Press 4" twice.
**Rules affected:** `restore` R9
**Suggested answer:** `intended` for this DAO — it has no duplicate check anywhere (create and rename rely on the manager too). The manager method that will call `restore` must refuse the restore with 409 when the name is taken; noted as follow-up FU-3.
**Answer:** intended (reviewer, 2026-10-11)
**Resolution:** rule unchanged. Rules: `restore` R9 ✅.

## Follow-ups for other reviews
> Decisions taken here that must be picked up when another module is reviewed. Nothing below is a rule of this DAO, and no bug is logged for any of it yet. No spec exists yet for the machine manager, service, endpoint or schema; whoever describes one of them must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machines endpoint** — `GET /machines/` (`app/api/v1/endpoints/machines.py`, `sort_by` / `sort_dir` query parameters, free text today) | An unknown sort field or sort direction (`sort_by=createdAt`, `sort_dir=DESC`) is silently answered with "name, ascending" and no error. The DAO's lenient fallback is intended (`search_advanced` R13, R15); whether the endpoint should reject unknown values with 422 (or accept upper case) is to be decided there. | Q2 — reviewer, 2026-10-10 |
| FU-2 | **Machine schema** (`app/schemas/machine.py`, `MachineCreate` / `MachineUpdate` — no trimming, no validators) and the **machine manager** review | A model number or manufacturer made only of spaces is stored as typed and then counts as "has a value" in the machines-page filters (`search_advanced` R10, R11 — intended at the DAO). Whether these two fields are trimmed, and whitespace-only stored as empty, when saved is to be decided there. | Q3 — reviewer, 2026-10-10 |
| FU-3 | **Machine manager / service / endpoint** (feature to build) | `DAOMachine.restore` is kept and specified, but nothing calls it: there is no "restore machine" endpoint, service or manager method, so a deleted machine cannot be put back through the application today. When it is built, the manager method must decide: 404 for a missing / other-workspace machine and what to answer for a machine that is not deleted (`restore` R4, R6); who restored and a "restored" activity entry (Q8); refusing a name now used by another live machine of the factory (Q9); and what to answer for a machine whose factory is soft-deleted (`restore` R7 — the DAO restores it and it stays hidden). | Q5 — reviewer, 2026-10-10 ("keep restore") |
| FU-4 | **Factory DAO / manager** review | The reviewer's reason for P1 / P2 is "we need to be able to put them back if the user undoes". Nothing restores a factory today: `DAOFactory.restore` exists and has no caller. The rules here (`get_by_factory` R3b, `get_by_section` R3b, `search_advanced` R3c) guarantee the machines come back once the factory is live again; the undo itself is to be raised in the factory review. | P1 / P2 — reviewer, 2026-10-10 |

## Overview
`DAOMachine` reads and soft-deletes rows of the `machines` table: one row per machine, always belonging to one workspace and one factory, optionally linked to one factory section through a separate assignment row. It serves the machines page (`search_advanced` ← `MachineManager.search_machines` ← `GET /machines/`), the "machines of a factory / section" lookups used by work-order generation (`app/utils/work_order_generation.py`) and by the machine manager's duplicate-name check (`get_by_factory`), and "delete machine" (`soft_delete` ← `MachineManager.delete_machine` ← `DELETE /machines/{id}/`). Many other managers fetch one machine through the inherited `get_by_id_and_workspace`. It also holds `restore`, the undo of "delete machine", which the reviewer decided to keep although nothing calls it yet. Invariants it is meant to protect: workspace isolation; soft-deleted machines never appearing in lists; and machines inside a soft-deleted factory or section being **hidden, never deleted or altered** — a machine is hidden by its factory's state alone and is back, unchanged, as soon as the factory is no longer deleted. It never commits; writes are flushed.

**Callables:** 5 specified (+ 1 section on inherited `BaseDAO` behavior specific to `Machine`) · 3 not specified
**Externals to mock:** `utcnow` (patch `app.dao.machine.utcnow`; used by `soft_delete` only — `restore` does not read the clock)
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` for the machines page are enforced by `GET /machines/`, not here.)

**Model facts (table `machines`, class `app.models.machine.Machine`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` (ON DELETE CASCADE) | — |
| `name` | String NOT NULL (no length limit, no unique constraint) | — |
| `is_running` | Boolean NOT NULL | `False` |
| `factory_id` | Integer NOT NULL, FK `factories.id` | — |
| `model_number`, `manufacturer` | String(200), nullable | `NULL` |
| `note` | Text, nullable | `NULL` |
| `created_at` | DateTime NOT NULL | `now()` (server default) |
| `created_by`, `updated_by`, `deleted_by` | Integer nullable, FK `profiles.id` | `NULL` |
| `updated_at` | DateTime nullable | `NULL`; set to `now()` by the database whenever an UPDATE is issued |
| `is_active` | Boolean NOT NULL | `True` |
| `is_deleted` | Boolean NOT NULL | `False` |
| `deleted_at` | DateTime nullable (naive UTC) | `NULL` |

- Soft delete of a machine = `is_deleted = True` together with `is_active = False`, `deleted_at`, `deleted_by`. Every list here looks only at `is_deleted`; **`is_active` and `is_running` are never used to hide a machine.** Nothing in the application sets a machine's `is_active` except `soft_delete` (to `False`) and `restore` (to `True`); the forms cannot change it.
- `machine.factory_section_id` / `machine.factory_section_name` are **read-only properties** (no setter): the section id / section name of the machine's assignment row, or `None` when the machine has no assignment.
- Assignment table `machine_section_assignments` (class `app.models.machine_section_assignment.MachineSectionAssignment`): NOT NULL `workspace_id`, `machine_id` (FK `machines.id`, CASCADE), `factory_section_id` (FK `factory_sections.id`, CASCADE); unique on `machine_id` (a machine has at most one section). No soft-delete column — unassigning deletes the row.
- `FactorySection` (`app.models.factory_section.FactorySection`): NOT NULL `workspace_id`, `name`, `factory_id`; `is_active` (default `True`), `is_deleted` (default `False`), `deleted_at`, `deleted_by`. Deleting a section through the application soft-deletes it and removes its assignment rows.
- `Factory` (`app.models.factory.Factory`): NOT NULL `workspace_id`, `name`, `abbreviation`; `is_active` (default `True`), `is_deleted` (default `False`); soft delete sets `is_deleted = True` and leaves `is_active` and the factory's machines untouched.
- Activity log `machine_activity_events` (class `app.models.machine_activity_event.MachineActivityEvent`): NOT NULL `workspace_id`, `machine_id`, `event_type` (string ≤ 50), `description` (text), `created_at` (naive UTC; Python-side default = current time); nullable `metadata_json` (Python attribute; database column `metadata`, type `json`), `performed_by`. A status change is a row with `event_type = "status_updated"` and `metadata_json = {"status": "<IDLE|RUNNING|OFF|MAINTENANCE>", ...}`. `MachineEventTypeEnum` (`app.models.enums`) members: `IDLE`, `RUNNING`, `OFF`, `MAINTENANCE` (value = name).
- Schemas (`app/schemas/machine.py`): `MachineCreate` = `name: str`, `factory_id: int`, `factory_section_id: int | None = None`, `model_number`, `manufacturer`, `note` (all `str | None = None`); `MachineUpdate` = the same six fields, all optional. No validators, no trimming, no length checks.

**Cross-spec notes (not rules of this DAO, not logged here):**
- `MachineManager._check_name_exists_in_factory` calls `get_by_factory` with the default `limit` of 100 and compares names with exact `==`: a duplicate machine name beyond the first 100 machines of a factory is missed (same shape as BUG-001 / BUG-002). To be raised in the machine manager's own spec.
- Work-order generation calls `get_by_section` / `get_by_factory` with `limit=1000` (BUG-342, already logged against `app/utils/work_order_generation.py`). The paging parameters of the DAO themselves are fine.
- `MachineManager.search_machines(include_deleted=True)` reads through the inherited `get_by_workspace` and is not reachable from the API (the service never passes the flag) — manager spec.
- The machines page shows each machine's current status through `MachineActivityEventDAO.get_latest_status_map`, which picks "latest" by timestamp only; after the BUG-886 fix the filter (R12a: ties → highest `id`) and the displayed status can disagree on a timestamp tie until that DAO is fixed too — to be raised in its own spec.

**Notes for the test designer:**
- Use the module singleton `machine_dao` (`from app.dao.machine import machine_dao`). All parameters after `db` are keyword-only.
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `FactorySection`, `Machine`, `MachineSectionAssignment` and `MachineActivityEvent` rows directly (add + flush) with the NOT NULL columns listed above. The session runs with `autoflush=False`: flush before calling the DAO.
- After creating an assignment row for a machine that is already loaded, call `db.expire_all()` (or expire the machine) before asserting `factory_section_id` / `factory_section_name`, otherwise the cached "no assignment" is read.
- **Name order (BUG-887, `search_advanced` R14):** the test database's collation (`English_United States.1252`) already sorts "apple, Banana, Zulu" case-insensitively, but on a case-only tie puts lower-case first regardless of `id`. Ascending: create machine "Bolt" first, then "bolt" → intended `["Bolt", "bolt"]`, today `["bolt", "Bolt"]`. Descending: create "bolt" first, then "Bolt" → intended `["bolt", "Bolt"]`, today `["Bolt", "bolt"]`. Both are deterministic → **strict** xfail. Cases that are not about BUG-887 must use names that differ in more than case.
- **Unordered lookups (BUG-343, `get_by_factory` R6, `get_by_section` R7):** today's order is whatever the database returns (usually insertion order). Insert names out of order ("Zulu" first, then "apple") and assert the intended order with a **non-strict** xfail; never weaken the assertion. Every other case of these two methods compares results as sets of ids.
- **Latest-status filter (BUG-886, `search_advanced` R12, R12a–R12e):** today every call with `latest_event_type` set raises `AttributeError`, so all these cases are **strict** xfail. Give status events **explicit, distinct** `created_at` values (e.g. `datetime(2026, 1, 1, 10, 0)`, `11:00`) unless the case is about a tie; for the tie case give both rows the same `created_at` and rely on insertion order for `id`. Assert results as lists of machine ids / names.
- **Soft-deleted factory (BUG-890, BUG-891):** build the factory with `is_active=True, is_deleted=True`; the "inactive but live" factory of `search_advanced` R3b is `is_active=False, is_deleted=False`. The machine inside it must itself be live. Keep at least one live machine in a live factory of the same workspace in the same case so the intended result is "only that machine". Today's result is deterministic (the machine is included) → **strict** xfail (for `get_by_factory` / `get_by_section` compare as sets, so BUG-343 does not interfere).
- **Factory no longer deleted (`get_by_factory` R3b, `get_by_section` R3b, `search_advanced` R3c):** start from a soft-deleted factory with a live machine, then set the factory's `is_deleted = False`, `deleted_at = None`, `deleted_by = None` directly on the row and flush (do not go through the factory DAO), then call the list. These hold today → plain pass cases. Take a snapshot of the machine's columns before and compare after.
- **Restore (`restore`):** no mock is needed. Build the deleted machine directly: `is_deleted=True, is_active=False, deleted_at=<a fixed naive datetime>, deleted_by=<an existing profile id>`. To see that no UPDATE was issued (R4) check `updated_at` is still `None` after `db.refresh(machine)`. For "not committed" (R5) use a savepoint: `db.begin_nested()`, restore, roll the savepoint back, `db.refresh(machine)`. R7a is two expected-to-fail checks: against `search_advanced` it fails for BUG-890, against `get_by_factory` / `get_by_section` for BUG-891 — one case per bug, both deterministic → **strict** xfail; the row-state part of that scenario (R7) is a pass case.
- **Soft-deleted section (BUG-889):** build the section with `is_deleted=True` and add the assignment row directly; machine and factory live. Deterministic today → **strict** xfail.
- **Search (BUG-888, BUG-892):** deterministic today → **strict** xfail. For BUG-888 use a workspace in which at least one machine does **not** contain the literal character, so "matches everything" is distinguishable.
- **Database errors:** a failing statement aborts the Postgres transaction. Wrap calls expected to raise `DataError` / `IntegrityError` in `with db.begin_nested():` so the session stays usable.
- `updated_at`: assert `None` → not `None`, never "later than". `deleted_at` is compared with the mocked `utcnow` value (a naive `datetime`).

## Not specified
- `DAOMachine.get_active_by_workspace` — dead code, to be removed (reviewer; Q4)
- (`get_by_factory` / `get_by_section`'s `include_deleted` parameter — dead parameter, to be removed (reviewer; Q6). The methods themselves are specified.)
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — not overridden; specified in `tests/unit/dao/base.spec.md`. Only what is specific to `Machine` is stated below ("Inherited `BaseDAO` methods on `Machine`").
- `machine_dao` — module-level singleton `DAOMachine(Machine)`, no logic
- `_SECTION_EAGER_LOAD` — module constant (loader option); its observable effect is stated in `get_by_factory` R8

---

## `DAOMachine.get_by_factory(db, *, factory_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineManager._check_name_exists_in_factory` with default paging; `resolve_template_machine_ids` in `app/utils/work_order_generation.py` with `limit=1000`)

**Purpose:** The live machines of one factory of a workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `factory_id` | int | equality on `machines.factory_id`; not validated (any integer, including `0`) |
| `workspace_id` | int | equality on `machines.workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `Machine` instances (possibly empty), each with its section assignment loaded.

**Rules:**
- **R1.** Returns the machines with `workspace_id` and `factory_id` equal to the arguments. A machine of the same factory id in another workspace, or of another factory in the same workspace, is never returned.
- **R2.** Soft-deleted machines (`is_deleted = True`) are never returned. `is_active` and `is_running` are not consulted: a machine with `is_active = False`, `is_deleted = False` is returned.
- **R3.** An unknown factory id, `factory_id=0`, an unknown workspace id, or a factory with no live machines returns `[]`.
- **R3a.** [BUG-891] (P2) When the factory itself is soft-deleted (`factories.is_deleted = True`), its machines are hidden: `[]` is returned even though it has live machines. They are hidden by the factory's state alone — nothing about the machines themselves says "deleted". *(Today: the factory row is never looked at — the live machines of a soft-deleted factory are returned.)*
- **R3b.** What surrounds R3a and holds today and after the fix: (1) the call changes nothing — the machines of a soft-deleted factory stay in the database exactly as they were (`is_deleted = False`, `is_active`, `deleted_at = None`, every other column and the section assignment row unchanged); (2) a factory that is live but inactive (`is_active = False`, `is_deleted = False`) hides nothing: its machines are returned; (3) once the factory is no longer deleted (`factories.is_deleted` back to `False`), its machines are returned again, unchanged, with nothing done to the machine rows.
- **R4.** `skip` and `limit` are applied after filtering: with defaults at most 100 machines are returned — given 101 live machines in the factory, exactly 100; soft-deleted machines never use up a place in the page. Consecutive windows (`skip=0, limit=2`, `skip=2, limit=2`, …) should partition the factory's machines with no repeats or gaps (relies on R6).
- **R5.** `limit=0` returns `[]`; `skip` at or past the number of matching machines returns `[]`. A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R6.** [BUG-343] Machines are ordered by name case-insensitive ascending, then `id` ascending, before `skip`/`limit` (HR-6). *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R7.** Each machine appears exactly once, whether or not it has a section assignment.
- **R8.** Section data is available on every returned machine: `factory_section_id` and `factory_section_name` give the assigned section's id and name, and both are `None` for a machine without an assignment.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `DAOMachine.get_by_section(db, *, factory_section_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `resolve_template_machine_ids` in `app/utils/work_order_generation.py`, with `limit=1000`)

**Purpose:** The live machines assigned to one factory section.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `factory_section_id` | int | equality on the assignment row's `factory_section_id`; not validated |
| `workspace_id` | int | equality on `machines.workspace_id` (the assignment row's and the section's own workspace are not checked) |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `Machine` instances (possibly empty), each with its section assignment loaded.

**Rules:**
- **R1.** Returns the machines of the workspace that have an assignment row pointing at `factory_section_id`. Machines without an assignment, and machines assigned to another section, are never returned.
- **R2.** Workspace isolation follows the machine: a machine of another workspace is never returned, even when its assignment points at the given section id. Soft-deleted machines (`is_deleted = True`) are never returned although their assignment row still exists; `is_active` and `is_running` are not consulted.
- **R3.** An unknown section id, `factory_section_id=0`, or a section with no assigned live machine in the workspace returns `[]`.
- **R3a.** [BUG-891] (P2) A machine whose factory is soft-deleted (`factories.is_deleted = True`) is hidden: it is not returned, although the machine, its assignment and the section are all live. *(Today: the factory row is never looked at — such a machine is returned.)*
- **R3b.** What surrounds R3a and holds today and after the fix: (1) the call changes nothing — the machine of a soft-deleted factory and its assignment row stay in the database exactly as they were; (2) a machine whose factory is live but inactive (`is_active = False`, `is_deleted = False`) is returned; (3) once the factory is no longer deleted, the machine is returned again, unchanged and still assigned to the same section, with nothing done to the machine or assignment rows.
- **R4.** [BUG-889] (HR-4) When the section itself is soft-deleted (`factory_sections.is_deleted = True`), `[]` should be returned even if assignment rows still point at it; the assignment rows are not changed. A section that is live but inactive (`is_active = False`) is unaffected. *(Today: the section row is never looked at — machines assigned to a soft-deleted section are returned.)*
- **R5.** Paging behaves as `get_by_factory` R4–R5 (defaults `skip=0`, `limit=100`; 101 assigned machines → exactly 100; `limit=0` → `[]`; negative values → the same `DataError`s).
- **R6.** Each machine appears exactly once (a machine has at most one assignment).
- **R7.** [BUG-343] Machines are ordered by name case-insensitive ascending, then `id` ascending, before `skip`/`limit` (HR-6). *(Today: no ordering is requested.)*
- **R8.** Every returned machine reports the section it was found through: `factory_section_id == factory_section_id` argument and `factory_section_name` = that section's name.

**Errors:** as `get_by_factory`.

**Side effects:** none

---

## `DAOMachine.soft_delete(db, *, db_obj, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `MachineManager.delete_machine` ← `DELETE /machines/{id}/`, which first answers 404 for a missing / other-workspace machine and 400 "Machine is already deleted" for a deleted one)

**Purpose:** Mark a machine as deleted, keeping the row.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `Machine` | the machine to delete; not checked for workspace or current state |
| `deleted_by` | int | profile id stored in `deleted_by`; must reference an existing profile (foreign key) — `None` is stored as `NULL` |

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a live machine, after the call `is_deleted = True`, `is_active = False`, `deleted_at` = the current time from `utcnow()` (naive UTC), `deleted_by` = the given id.
- **R2.** No other column is changed by the method: `name`, `factory_id`, `workspace_id`, `model_number`, `manufacturer`, `note`, `created_by`, `created_at`, `updated_by` keep their values (no `updated_by` stamp), and `is_running` is left as it was — a running machine stays `is_running = True`. `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R3.** The machine's section assignment row is kept: after the delete the row still exists and `db_obj.factory_section_id` still gives the section id.
- **R4.** Given a machine that is already soft-deleted, no error is raised and the deletion stamp is overwritten: `deleted_at` becomes the new `utcnow()` value and `deleted_by` the new id. (The manager refuses this case before calling.)
- **R5.** The change is flushed and not committed: in the same session the machine is no longer returned by `get_by_factory`, `get_by_section` or `search_advanced`, and is still returned by the inherited `get_by_id_and_workspace`; rolling back makes it live again. The returned object is the very instance passed in. `restore` undoes the delete (`restore` R8).
- **R6.** No workspace check: the machine passed in is deleted whatever workspace it belongs to (the caller is responsible for the lookup).
- **R7.** Given a `deleted_by` that is not an existing profile id, the flush fails (see Errors) and nothing is saved.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `deleted_by` references no profile | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` | — (not asserted) |

**Side effects:** one `machines` row updated (`is_deleted`, `is_active`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed; no commit; no activity event (the manager writes the "deactivated" event).

---

## `DAOMachine.restore(db, *, db_obj)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: nothing today — kept by reviewer decision, Q5; the "restore machine" feature that will call it is not built yet, see Follow-ups FU-3)

**Purpose:** Bring a soft-deleted machine back, exactly as it was — the undo of `soft_delete`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `Machine` | the machine to restore; not checked for workspace, for its current state, or for the state of its factory or section |

There is no "who" argument: the method cannot record the acting user.

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a soft-deleted machine (`is_deleted = True`, `is_active = False`, `deleted_at` and `deleted_by` set), after the call `is_deleted = False`, `is_active = True`, `deleted_at = None`, `deleted_by = None` — in the database, not only on the object.
- **R2.** No other column is changed by the method: `name`, `factory_id`, `workspace_id`, `model_number`, `manufacturer`, `note`, `created_by`, `created_at` keep their values, and `is_running` is left as it was — a machine deleted while `is_running = True` comes back with `is_running = True`. `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R2a.** ✅ (Q8) Nobody is recorded as having restored the machine: `updated_by` keeps the value it had (including `None`), and no row is added to the machine's activity log (`machine_activity_events`).
- **R3.** The machine's section assignment is neither created, changed nor removed: a machine that had an assignment row still has the same one after the restore and `db_obj.factory_section_id` gives the same section id; a machine without an assignment still has none (`factory_section_id` is `None`).
- **R4.** The current state is not checked and no error is raised for a machine that is not deleted. Given a machine that is already live and active (`is_deleted = False`, `is_active = True`, no deletion stamp), nothing changes at all: no UPDATE is issued, so `updated_at` stays as it was (e.g. `None`). Given a live machine with `is_active = False`, `is_active` becomes `True` (and `updated_at` is set); it stays not deleted.
- **R5.** The change is flushed and not committed: in the same session the machine is returned again by `get_by_factory`, by `search_advanced`, and (if it has an assignment) by `get_by_section` — given its factory is live; rolling back makes it soft-deleted again with its previous `deleted_at`, `deleted_by` and `is_active = False`. The returned object is the very instance passed in (`result is db_obj`).
- **R6.** No workspace check: the machine passed in is restored whatever workspace it belongs to (the caller is responsible for the lookup). Other machines — of the same factory, of other factories, deleted or live — are never touched: restoring one deleted machine leaves a second deleted machine of the same factory deleted.
- **R7.** The factory is not looked at and never changed. Given a soft-deleted machine whose factory is itself soft-deleted, the restore succeeds with no error: the machine row becomes live exactly as in R1, and the factory row stays as it was (`is_deleted = True`, its `deleted_at` / `deleted_by` unchanged).
- **R7a.** [BUG-890] [BUG-891] (P1, P2) A machine restored per R7 stays hidden for as long as its factory is soft-deleted: it is not returned by `search_advanced` (`search_advanced` R3a — BUG-890) nor by `get_by_factory` / `get_by_section` (their R3a — BUG-891). It appears in all three as soon as the factory is no longer deleted, with nothing further done to the machine (their R3b / R3c). *(Today: the factory row is never looked at — the machine is listed by all three right after the restore, while its factory is still deleted.)*
- **R8.** Restore is the undo of `soft_delete`: a live, active machine that is soft-deleted and then restored has the same value in every column as before the delete — except `updated_at` (set by the database) — its deletion stamp is empty again, its section assignment is the same row, and it is listed again where it was listed before. (The one thing not brought back: a machine that had `is_active = False` before it was deleted comes back with `is_active = True` — R1. No application path produces such a machine.)
- **R9.** ✅ (Q9) No name check is made: given a soft-deleted machine "Press 4" and another, live machine "Press 4" in the same factory, the restore succeeds and both are live afterwards; the other machine is not changed.

**Errors:** none. (Nothing the method writes can violate a constraint: it only clears `deleted_by` and sets two booleans.)

**Side effects:** at most one `machines` row updated (`is_deleted`, `is_active`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed; no UPDATE when the machine is already live and active; no commit; no activity event; no other table written.

---

## `DAOMachine.search_advanced(db, *, workspace_id, factory_id=None, factory_section_id=None, is_running=None, search=None, has_model_number=None, has_manufacturer=None, latest_event_type=None, sort_by="name", sort_dir="asc", skip=0, limit=100)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `MachineManager.search_machines` ← `MachineService.get_machines` ← `GET /machines/`. The endpoint enforces `skip >= 0`, `1 <= limit <= 1000`; `sort_by` / `sort_dir` / `search` are free text there. For the maintenance-window filter and the `maintenance_date` sort the manager calls it with `skip=0, limit=10_000` and pages in Python.)

**Purpose:** One page of the machines list of a workspace, with the machines page's filters and sort order.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | workspace to restrict to |
| `factory_id` | int \| `None` | `None` = all factories; any integer (including `0`) filters |
| `factory_section_id` | int \| `None` | `None` = all machines, assigned or not; any integer (including `0`) filters |
| `is_running` | bool \| `None` | `None` = both; `True` / `False` filter on `machines.is_running` |
| `search` | str \| `None` | free text; `None` and `""` = no search |
| `has_model_number` | bool \| `None` | `None` = no filter |
| `has_manufacturer` | bool \| `None` | `None` = no filter |
| `latest_event_type` | `MachineEventTypeEnum` \| `None` | `None` = no filter |
| `sort_by` | str, default `"name"` | `"name"` or `"created_at"`; anything else behaves as `"name"` |
| `sort_dir` | str, default `"asc"` | exactly `"desc"` = descending; anything else = ascending |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `Machine` instances (possibly empty), each with its section assignment loaded (`factory_section_id` / `factory_section_name` usable, `None` when unassigned).

**Rules:**
- **R1.** Only machines with `workspace_id` equal to the argument are returned; a machine of another workspace is never returned, whatever the other filters. An unknown workspace id returns `[]`.
- **R2.** Soft-deleted machines (`is_deleted = True`) are never returned and never use up a place in the page. There is no way to include them. `is_active` is not consulted: a machine with `is_active = False`, `is_deleted = False` is returned.
- **R3.** With no optional filter, every live machine of the workspace is returned (paged), whether or not it has a section assignment, each exactly once.
- **R3a.** [BUG-890] (P1) A machine whose factory is soft-deleted (`factories.is_deleted = True`) is hidden — by the factory's state alone, the machine itself being live — and should never be returned: not without a factory filter, not when that factory's own id is given as `factory_id`, and whatever the other filters; it should not use up a place in the page. Example: Factory A live with machine "Lathe", Factory B soft-deleted with machine "Press" → with no filter only "Lathe"; with `factory_id` = B `[]`; with `limit=1` and `sort_dir="desc"` the single row is "Lathe". *(Today: the factory row is never looked at — both machines are returned, "Press" alone for `factory_id` = B, and "Press" for the `limit=1` descending case.)*
- **R3b.** What does not hide a machine (holds today and after the fix): a machine whose factory is live but inactive (`factories.is_active = False`, `is_deleted = False`) is returned like any other. Searching never changes anything: the machine row of a soft-deleted factory stays in the table as it was (`is_deleted = False`).
- **R3c.** A machine hidden per R3a comes back by itself (holds today and after the fix): once its factory is no longer deleted (`factories.is_deleted` back to `False`), the machine is returned again — with no filter and for that factory's id — with every column and its section assignment exactly as before the factory was deleted, and with nothing done to the machine row. Example: Factory B soft-deleted with machine "Press" (running, model number "P-4", assigned to section "Line 1") → Factory B restored → "Press" is listed, still running, model number "P-4", section "Line 1".
- **R4.** Given any integer `factory_id`, only machines with that `factory_id` are returned; `factory_id=0` or an unknown id returns `[]`; `None` applies no factory filter.
- **R5.** Given any integer `factory_section_id`, only machines with an assignment row pointing at that section are returned — unassigned machines and machines of other sections are excluded; `factory_section_id=0` or an unknown id returns `[]`; `None` applies no section filter. Each matching machine appears exactly once.
- **R6.** `factory_id` and `factory_section_id` given together must both match (a section id of another factory than `factory_id` returns `[]`).
- **R6a.** [BUG-889] (HR-4) Given the id of a soft-deleted section (`factory_sections.is_deleted = True`), `[]` should be returned even if assignment rows still point at it. Without a section filter, a machine with such a left-over assignment is still listed (the machine itself is live). *(Today: the section row is never looked at — machines assigned to the soft-deleted section are returned for its id.)*
- **R7.** `is_running=True` returns only machines with `is_running = True`; `is_running=False` only those with `is_running = False`; `None` returns both.
- **R8.** [BUG-892] (P3) `search=None`, `search=""` and a whitespace-only `search` (e.g. `"   "`, `"\t"`, `" \n "`) apply no search filter. Otherwise leading / trailing whitespace is removed before matching (`" bolt "` and `"\tbolt\n"` find "Bolt cutter"); inner whitespace is kept as typed. "Whitespace" is what Python's `str.strip()` removes — spaces, tabs and newlines included (reviewer, 2026-10-10). *(Today: `None` and `""` apply no filter — that part holds — but the text is used untrimmed: `" bolt "` matches only values containing the word with both spaces, and `"   "` matches only machines whose name, model number or manufacturer contains three consecutive spaces.)*
- **R9.** [BUG-888] (HR-8) A search matches a machine when the text is a case-insensitive **literal** substring of its `name`, its `model_number` or its `manufacturer` (any one is enough; `"BOLT"` finds "bolt" and "Bolt cutter"; `"sie"` finds a machine whose manufacturer is "Siemens"). A `NULL` model number / manufacturer simply does not match. `note`, the factory name and the section name are not searched. `%`, `_` and `\` are matched literally: `%` alone finds only machines containing `%` (e.g. model number "50%"), `_` alone only those containing `_`, `a\b` finds name `a\b` and not `ab`. *(Today: `%` and `_` are not escaped and act as wildcards — `%` alone or `_` alone matches every machine; `\` is the `ILIKE` escape character, so `a\b` matches "ab" and not `a\b`.)*
- **R10.** ✅ (Q3) `has_model_number=True` returns only machines whose `model_number` is neither `NULL` nor the empty string `""`; `has_model_number=False` returns only machines whose `model_number` is `NULL` or `""`; `None` applies no filter. A whitespace-only model number (`"   "`) counts as having one.
- **R11.** ✅ (Q3) `has_manufacturer` behaves exactly as R10 on `manufacturer`, independently of `has_model_number`.
- **R12.** [BUG-886] (Q1) Given a `latest_event_type`, the call succeeds and returns only the machines whose latest status change has that status, where a status change is an activity row of that machine with `event_type = "status_updated"` and its status is the `"status"` value of the row's `metadata_json`. `latest_event_type=None` applies no status filter (holds today). *(Today: every call with `latest_event_type` set — any of the four values, with or without matching data — raises `AttributeError` while the query is built; no query is sent.)*
- **R12a.** [BUG-886] "Latest" is the status change with the greatest `created_at`; among rows sharing that `created_at`, the one with the greatest `id`. Example: machine A has RUNNING at 10:00 and IDLE at 11:00 → A matches `IDLE` and not `RUNNING`. Machine C has RUNNING and then OFF, both at 11:00 (OFF inserted second) → C matches `OFF` only. *(Today: `AttributeError`.)*
- **R12b.** [BUG-886] A machine with no status change never matches any `latest_event_type`. Activity rows of other types (`"created"`, `"updated"`, `"deactivated"`, …) are ignored even when newer and even when their metadata has a `"status"` key. *(Today: `AttributeError`.)*
- **R12c.** [BUG-886] A latest status change whose `metadata_json` is `NULL`, or has no `"status"` key, matches no `latest_event_type`; older status changes of that machine are not consulted instead. *(Today: `AttributeError`.)*
- **R12d.** [BUG-886] Only status changes recorded in the given workspace count (`machine_activity_events.workspace_id == workspace_id`). *(Today: `AttributeError`.)*
- **R12e.** [BUG-886] Each matching machine appears exactly once, also when two status changes with the same status share the newest `created_at`; the filter combines with all other filters (R13a), sorting and paging like any other. *(Today: `AttributeError`.)*
- **R13.** ✅ (Q2) `sort_by="name"` sorts by machine name, `sort_by="created_at"` by creation time; any other value (e.g. `"maintenance_date"`, `"createdAt"`, `""`) sorts by name, with no error.
- **R13a.** All given filters combine with AND; the three search alternatives (name, model number, manufacturer) combine with OR.
- **R14.** [BUG-887] (HR-6) Sorting by name is case-insensitive: ascending gives "apple", "Banana", "Zulu"; descending the reverse. Machines whose names differ only in case, or are identical, come back in `id` ascending order — in both directions. *(Today: the name is compared with the database's default collation, so a case-only difference is decided by the collation instead of the `id` — on the test database "bolt" always sorts before "Bolt" ascending and after it descending.)*
- **R15.** ✅ (Q2) `sort_dir="desc"` (exactly, lower-case) sorts descending; any other value (`"asc"`, `"DESC"`, `"descending"`, `""`) sorts ascending, with no error.
- **R16.** Sorting by `created_at` puts the earliest-created machine first ascending and last descending; machines with the same `created_at` come back in `id` ascending order in both directions. (All rows inserted in one test transaction share `created_at` unless it is set explicitly.)
- **R17.** `skip` and `limit` are applied after all filtering and ordering, so consecutive windows partition the matching machines with no repeats or gaps. With defaults at most the first 100 are returned — given 101 matching machines, exactly 100.
- **R18.** `limit=0` returns `[]`; `skip` at or past the number of matching machines returns `[]`. A negative `limit` or `skip` makes Postgres reject the query (see Errors).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |
| *(today only — BUG-886)* `latest_event_type` is not `None` | `AttributeError` | — |

**Side effects:** none

---

## Inherited `BaseDAO` methods on `Machine`
**Shape:** create / update / get
**Persistence:** writes / reads
**Visibility:** public (used by: `MachineManager.create_machine` (`create`, dict), `update_machine` and `create_machine_event` (`update`, dict), and `get_by_id_and_workspace` from more than ten managers and services; `get_by_workspace` from the unreachable `include_deleted` branch of `MachineManager.search_machines`; `get` from `ProductionLineManager`)

**Purpose:** `DAOMachine` overrides none of the generic methods; the base spec (`tests/unit/dao/base.spec.md`) applies. The rules below state only what the `Machine` model changes.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `name`, `factory_id` creates a machine with `is_running = False`, `is_active = True`, `is_deleted = False`, `created_at` set, `updated_at = None`, `model_number` / `manufacturer` / `note` / `deleted_at` / `deleted_by` = `None`, and `factory_section_id` reading `None` (no assignment row is created).
- **R2.** ✅ (Q7) `create` with a `MachineCreate` schema always raises `AttributeError` — the schema always carries `factory_section_id` (default `None`), which is a read-only property of `Machine` — and no machine is added. The same happens for a dict that contains the key `factory_section_id`.
- **R3.** `update` with a dict of real columns (e.g. `{"name": "B", "updated_by": 7}`, `{"is_running": True}`) behaves as base spec `update` R1, R7, R8. `update` with a `MachineUpdate` in which `factory_section_id` was not set, or was set explicitly to `None`, applies the other given fields and raises nothing (the field is dropped — base spec `update` R2, R3).
- **R4.** ✅ (Q7) `update` with a dict containing the key `factory_section_id` (any value, including `None`), or with a `MachineUpdate` whose `factory_section_id` is set to a number, raises `AttributeError`; nothing is flushed — after `db.refresh(machine)` every column has its old value — and no assignment row is created or changed.
- **R5.** The raw lookups stay raw (HR-4 scope): `get`, `get_by_id_and_workspace` and `get_by_workspace` return soft-deleted machines, and machines of soft-deleted factories, like any other (base spec `get` R3, `get_by_id_and_workspace` R4, `get_by_workspace` R4). Hiding them is the calling manager's decision.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `factory_section_id` passed to `create` / `update` (R2, R4) | `AttributeError` | — (text depends on the Python version; not asserted) |

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16 | eager load of assignment → section on every list | `get_by_factory` R7, R8; `get_by_section` R6, R8; `search_advanced` Returns, R3 |
| 28, 41 | defaults `include_deleted=False`, `skip=0`, `limit=100` | `get_by_factory` R4; `get_by_section` R5 (`include_deleted`: Not specified, Q6) |
| 31–34 | `workspace_id` AND `factory_id`; no join to `factories` (BUG-891) | `get_by_factory` R1, R3, R3a, R3b |
| 35–36 | `if not include_deleted:` → `is_deleted == False` (the `True` side is the dead parameter, Q6) | `get_by_factory` R2 |
| 37 | offset / limit, no `ORDER BY` (BUG-343); `limit=0`; negative values | `get_by_factory` R4, R5, R6, Errors |
| 44–49 | inner join to the assignment; machine `workspace_id` AND assignment `factory_section_id`; no check of the section row (BUG-889) or the factory row (BUG-891) | `get_by_section` R1, R2, R3, R3a, R3b, R4, R6, R8 |
| 50–51 | `if not include_deleted:` → `is_deleted == False` (the `True` side is the dead parameter, Q6) | `get_by_section` R2 |
| 52 | offset / limit, no `ORDER BY` (BUG-343) | `get_by_section` R5, R7 |
| 54–66 | `get_active_by_workspace` | Not specified (Q4) |
| 72–75 | four fields set unconditionally (already-deleted machine → stamp overwritten); `utcnow()` | `soft_delete` R1, R2, R3, R4, R6 |
| 76–78 | add + flush (FK on `deleted_by`), return same instance, no commit | `soft_delete` R5, R7, Errors |
| 84–87 | four fields reset unconditionally — no check of the machine's state (already live → no change; live but inactive → activated), of its workspace, of its factory (BUG-890 / BUG-891 decide visibility), or of its name; no user argument | `restore` R1, R2, R2a, R3, R4, R6, R7, R7a, R8, R9 |
| 88–90 | add + flush, return same instance, no commit | `restore` R5 |
| 110–113 | always `workspace_id` AND `is_deleted == False`; no `is_active`; no join to `factories` (BUG-890) | `search_advanced` R1, R2, R3, R3a, R3b, R3c |
| 115–116 | `if factory_id is not None:` — given (incl. `0`) / `None` | `search_advanced` R4, R6 |
| 118–121 | `if factory_section_id is not None:` — inner join to the assignment, given (incl. `0`) / `None`; section row not checked (BUG-889) | `search_advanced` R5, R6, R6a |
| 123–124 | `if is_running is not None:` — `True` / `False` / `None` | `search_advanced` R7 |
| 126 | `if search:` — `None` / `""` skip; whitespace-only is truthy (BUG-892) | `search_advanced` R8 |
| 127–134 | `ILIKE '%text%'` on name OR model number OR manufacturer; untrimmed (BUG-892), unescaped (BUG-888) | `search_advanced` R8, R9, R13a |
| 136–139 | `has_model_number is True` / `is False` / `None` | `search_advanced` R10 |
| 141–144 | `has_manufacturer is True` / `is False` / `None` | `search_advanced` R11 |
| 146 | `if latest_event_type is not None:` — `None` skips | `search_advanced` R12 |
| 147–158 | newest `created_at` per machine among `status_updated` rows of the workspace | `search_advanced` R12a, R12b, R12d |
| 160–177 | status of the row(s) at that timestamp; `.astext` on a generic `JSON` column raises `AttributeError` (BUG-886); no tie-break on `id` | `search_advanced` R12, R12a, R12c, R12e, Errors |
| 179–182 | inner join machines ↔ latest status, status == enum value | `search_advanced` R12, R12b, R12e |
| 184–188 | `sort_field_map.get(sort_by, Machine.name)` — `name` / `created_at` / unknown → name | `search_advanced` R13, R16 |
| 189 | `sort_dir == "desc"` → descending / anything else → ascending | `search_advanced` R15 |
| 191 | `ORDER BY <column>, machines.id ASC` (collation-dependent name comparison, BUG-887), then offset / limit; `limit=0`; negative values | `search_advanced` R14, R16, R17, R18, Errors |
| `base.py` 76–84 | `create`: dict / schema → `Machine(**data)`; read-only property `factory_section_id` | inherited R1, R2 |
| `base.py` 108–119 | `update`: dict / schema (`exclude_unset`, `exclude_none`); `hasattr` true for the property → `setattr` fails | inherited R3, R4 |
| `base.py` 43, 161–167, 187–194 | raw lookups: no `is_deleted` filter, no factory check | inherited R5 |
