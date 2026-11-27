# Spec — `app/managers/machine_section_assignment_manager.py`

> **Status:** APPROVED (2026-10-16)
> **Source commit:** e48a092

> **Review round 2026-10-16.** The reviewer delegated every open decision of this spec to Claude. Decided by Claude under the reviewer's delegation (2026-10-16): every suggested answer is accepted — P1 (bug, BUG-910), P2 (intended), Q1 (intended) and the lines citing house rules / reused bugs (BUG-906, BUG-907, BUG-908, BUG-909; no new ID for them). None of these is the reviewer's own answer. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed. BUG-910 is logged in `docs/testing/bugs.md` with the delegation wording. `clear_for_section` stays on the dead-code list ("remove together with the fix of BUG-908") and is specified and tested as it behaves today.

> **Pilot convention:** every question below carried a suggested answer, applied to the rules as a provisional default. All were accepted on 2026-10-16 (decided by Claude under the reviewer's delegation); nothing is provisional any more.
>
> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10).
> 2. Things belonging to a soft-deleted factory or section are **hidden by the parent's state, their own rows untouched**, so that restoring the parent brings them back ("hidden, not cascaded" — machine DAO P1 / P2, factory section DAO; confirmed 2026-10-11). A section of a soft-deleted factory is hidden (BUG-904).
> 3. BUG-908 (accepted 2026-10-16, assignment DAO spec P3): deleting a section must not erase its assignments. When it is fixed, `clear_for_section` of this manager loses its only caller and is removed (`docs/testing/dead-code-removal-checklist.md`, "remove together with the fix of BUG-908"). It is reachable today, so it is specified and tested as it behaves today.
> 4. Bugs of the assignment DAO that this manager only passes through (BUG-906, BUG-907, BUG-909) are cited on the manager's rules with the same ID; no duplicate is logged.
> 5. Raw DAO lookups return soft-deleted rows; the manager decides what to refuse (base DAO spec, HR-4 scope).
>
> **Verified by running** (throwaway script against the test database, rolled back): every "Today:" note below; every status code and detail message; `set_assignment` creating, re-saving the same section (new `id`, `created_by` = second user), moving, clearing (with and without a row, with an unknown machine id, with a bogus `factory_id`, with an unknown `workspace_id`), the 404 for an unknown id, for `0`, for `-1` and for a section of another workspace, the 400 for a deleted section (also when it belongs to another factory — the "deleted" message wins), the 400 for a section of another factory and for a `factory_id` that matches no factory, that the machine's existing row is unchanged after each refusal; acceptance today of an inactive section, a section of a soft-deleted factory, a soft-deleted machine, a machine of another factory than the `factory_id` passed, a machine of another workspace; the foreign-key error for an unknown machine and an unknown user, `user_id=None`, the unique violation for a machine whose row is in another workspace; that a machine already loaded still reports its old section after `set_assignment` until expired; keyword-only arguments of both methods; `clear_for_section` returning the machine ids (soft-deleted machine included), leaving rows of other sections and of another workspace pointing at the same section, refreshing a machine already loaded (its section reads `None` afterwards; a name changed in memory before the call keeps its new value), machines not loaded before, an unknown section (`[]`), savepoint rollback; the 10 000 cap through the manager (10 001 rows → 10 000 ids, 1 row left; a second call returns 1 id). **Not run:** anything at the HTTP level; the *intended* behavior of the bug rules. **Row order:** never relied on — the order of the ids returned by `clear_for_section` is unspecified today and not deterministic on the test database.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted (decided by Claude under the reviewer's delegation, 2026-10-16)
| # | What the code does today | Answer (accepted) |
|---|---|---|
| P1 | A machine can be put into a section whose factory has been deleted. Such a section is hidden everywhere else, but here it is accepted like a live one | bug — refuse it exactly like a deleted section (400 "Cannot assign a machine to a deleted factory section"); nothing is saved — BUG-910 |
| P2 | After putting a machine into a section, a copy of that machine already held in memory still shows the old section until it is reloaded. Both callers reload it themselves, so no screen shows a wrong value | intended — reloading is the caller's job (same decision as for the assignment DAO) |
| Q1 | The manager never looks at the machine itself: it does not check that the machine exists in the workspace, is not deleted, or really belongs to the factory it is told. Both callers (create machine, edit machine) check this before calling | intended — the callers own the machine checks; the manager checks only the section |

Nothing here needs the owner (no money, no order workflow).

Already decided by house rules / existing bugs (cited, no new ID; kept as applied — decided by Claude under the reviewer's delegation, 2026-10-16):
- Saving a machine with **the section it already has** throws its link away and writes a new one (new id, "created by" = whoever saved) → BUG-909 (HR-9, assignment DAO). `set_assignment` R4.
- "Unassign every machine of a section" handles at most 10 000 machines → BUG-907 (assignment DAO). `clear_for_section` R3.
- The machine ids it returns come in no defined order → BUG-906 (HR-6, assignment DAO). `clear_for_section` R7.
- That "delete section" calls `clear_for_section` at all → BUG-908 (logged against `app/managers/factory_section_manager.py`; the fix is there, then this method is removed). `clear_for_section` Visibility.

### House-rule violations — applied automatically
None of its own. The house-rule bugs reached through this manager are the assignment DAO's (BUG-906 HR-6, BUG-909 HR-9), cited above with their IDs — kept as applied, decided by Claude under the reviewer's delegation (2026-10-16).

Checked and **not** violated: **HR-4** — the section is read with the raw by-id lookup (which returns deleted rows, as HR-4's scope allows) and a deleted section is then refused explicitly (`set_assignment` R7); the case of a deleted *factory* is not a house-rule matter but standing decision 2 — P1. **HR-9** — beyond BUG-909, nothing is stamped. **HR-10** — no money, stock or approval: no lock. **HR-2, HR-5–HR-8** — no names, lists or search. **HR-14** — `clear_for_section` is not a background batch.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-10-16)

### P1. A section of a deleted factory is accepted — 🐞 BUG-910
**Background:** A factory is soft-deleted (`is_deleted = True`, the row stays). By the standing decision "hidden, not cascaded", its sections keep their own rows (`is_deleted = False`) and are hidden by the factory's state: the section list hides them (BUG-904), the machine lookups hide the machines of a deleted factory (BUG-891). `set_assignment` refuses a section that is itself deleted (400), but never looks at the section's factory. Creating a machine in a deleted factory, or editing one that is in a deleted factory, is not refused by the machine manager today (factory manager FU-5), so this case is reachable from `POST /machines/` and `PUT /machines/{id}/`.
**What happens today:** Given a live section "Paint" of the deleted factory "Old Plant" and a machine of "Old Plant", `set_assignment` saves the link and returns it (verified).
**Example:** "Old Plant" was deleted last week. A user edits the machine "Sprayer 1" (still in "Old Plant") and picks section "Paint" from a stale form: 200, the machine is now "in Paint" — a section nobody can see in the section list. Had "Paint" itself been deleted, the user would have got 400.
**Rules affected:** `set_assignment` R9 (tagged)
**Answer:** bug — per BUG-684 / BUG-904 precedent (`write-to-soft-deleted-related-row`; standing decision 2): a section whose factory has `is_deleted = True` is refused like a deleted section — 400 `Cannot assign a machine to a deleted factory section`, nothing written, the machine's existing link unchanged. The check comes after the "other factory" check (a section of another factory still gets that message). An inactive-but-live factory is not refused. Clearing (`factory_section_id = None`) stays allowed.
**Resolution:** 🐞 BUG-910 (pattern `write-to-soft-deleted-related-row`; the fix is in `app/managers/machine_section_assignment_manager.py`) — decided by Claude under the reviewer's delegation (2026-10-16). Rules: `set_assignment` R9.

### P2. A machine already loaded is not refreshed after `set_assignment` — ✅ intended
**Background:** A machine reads its section through its assignment row (`machine.factory_section_id` is a read-only shortcut over `machine.section_assignment`). SQLAlchemy keeps a machine that was already read in memory for the rest of the request. For the assignment DAO the same behavior was decided `intended`: refreshing objects already in memory is the caller's job (assignment DAO Q1, 2026-10-16). This manager's own `clear_for_section` does refresh the machines it touches (R5 there); `set_assignment` does not.
**What happens today:** A machine whose section was read before the call still reports the old section afterwards (also after clearing), until it is expired or reloaded (verified). Both callers expire it right after the call (`MachineManager.create_machine`, `update_machine`), so no response shows a stale section.
**Example:** A developer adds a third caller of `set_assignment` and returns the machine without expiring it: the response says "section: Cutting" although the machine was just moved to "Paint".
**Rules affected:** `set_assignment` R12
**Answer:** intended — per assignment DAO Q1 precedent: reloading is the caller's job; both callers do it. Answer `bug — set_assignment expires the machine's section_assignment itself, like clear_for_section` if callers should be able to rely on it.
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-16): the suggested answer is accepted; no bug, no ID. Rules: `set_assignment` R12 ✅.

### New questions

### Q1. The manager never looks at the machine — ✅ intended
**Background:** `set_assignment` receives `machine_id` and `factory_id` from its caller and checks only the section: that it exists in the workspace, is not deleted, and belongs to `factory_id`. The docstring says it "validates the section belongs to the same factory as the machine" — it compares with the `factory_id` it is given, not with the machine's stored factory. Its two callers look the machine up first: `create_machine` has just created it in the workspace with that factory; `update_machine` refuses a missing, other-workspace (404) or deleted (400) machine and passes the machine's (possibly new) factory. The assignment DAO checks nothing either (assignment DAO `upsert_for_machine` R6).
**What happens today:** Called directly, `set_assignment` saves a link for a soft-deleted machine, for a machine of another workspace (stored under the caller's workspace) and for a machine of factory B when told `factory_id = A` and given a section of A (all verified). An unknown machine id fails only in the database (foreign-key error, not a 404).
**Example:** No API path can do this today. A future caller (e.g. a bulk "move machines to section" endpoint) that forgets to check the machine could put a machine of another workspace into one of this workspace's sections.
**Rules affected:** `set_assignment` R10, R11
**Answer:** intended — the manager is a helper of the machine manager, which owns the machine checks; it validates only what it reads (the section). The docstring should say "the factory passed by the caller" (no bug, no ID). Answer `bug — set_assignment loads the machine (404 if missing / other workspace, 400 if deleted) and compares the section's factory with the machine's own factory` if it should protect itself.
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-16): the suggested answer is accepted; the docstring is to be corrected when the file is next touched; no bug, no ID. Rules: `set_assignment` R10 ✅, R11 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here except where an ID is given. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Factory section manager** (`app/managers/factory_section_manager.py`, next module) | (a) `delete_factory_section` calls `machine_section_assignment_manager.clear_for_section` right after soft-deleting the section: tag its "delete keeps the section's assignments" rule with **BUG-908** (already logged there — no new ID). Today that call also brings BUG-907 (10 000 cap) and BUG-906 (order) into the delete; after the fix both disappear with the call. The fix also drops the import at `factory_section_manager.py:13-15` (dead-code list). (b) Today the delete leaves no machine in memory showing the deleted section — this manager expires each one (`clear_for_section` R5); after the fix nothing needs expiring. (c) Section create / rename / move into a **soft-deleted factory** (section DAO FU-2 (h)): if P1 here is accepted (BUG-910 — a section of a deleted factory is treated like a deleted section), the section manager should refuse those writes for the same reason. (d) The section manager uses the same raw `get_by_id_and_workspace` and the same 404 text `Factory section with ID <id> not found` as this manager — keep the two consistent. | P1, BUG-908 |
| FU-2 | **Machine manager** (`app/managers/machine_manager.py`) | (a) Q1: the machine checks (exists in workspace, not deleted, its factory) are the machine manager's job — `create_machine` and `update_machine` must keep doing them before calling `set_assignment`. (b) P2: both must keep expiring `section_assignment` after the call. (c) `update_machine` calls `set_assignment` whenever `factory_section_id` is in the request, so every such edit re-stamps the link (BUG-909). (d) Assignment DAO FU-3 stands: changing `factory_id` without sending `factory_section_id` keeps a section of the old factory. (e) Creating / editing a machine in a soft-deleted factory is not refused (factory manager FU-5); with P1 accepted, sending a section of that factory gets 400, while sending none succeeds. | Q1, P1, P2 |

## Overview
`MachineSectionAssignmentManager` sets, changes or clears the optional section of a machine ("Press 4 is in Cutting") and, when a section is deleted, unassigns all its machines. `set_assignment` is called by `MachineManager.create_machine` (when `factory_section_id` is given) and `MachineManager.update_machine` (whenever `factory_section_id` is in the request, including `null`) behind `POST /machines/` and `PUT /machines/{id}/`. `clear_for_section` is called only by `FactorySectionManager.delete_factory_section` behind `DELETE /factory-sections/{id}/` (BUG-908 — that call is to go, and this method with it). The invariants it protects: a machine is only put into a live section of the caller's workspace that belongs to the factory the caller names; at most one section per machine (the DAO / database). The manager never commits; the DAO flushes.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none (no clock is read; `created_at` is set by the database)
**Integration-only behavior:** the machine checks done by the callers before `set_assignment` (Q1); the 404 / 400 reaching the client as JSON; the services' commit / rollback.

**Facts for the test designer**
- Import: `from app.managers.machine_section_assignment_manager import MachineSectionAssignmentManager, machine_section_assignment_manager`. `MachineSectionAssignmentManager()` takes no arguments; the module instance holds no per-call state and can serve every test. Every parameter after `session` is **keyword-only** in both methods (a positional call raises `TypeError`).
- `HTTPException` is `fastapi.HTTPException`; assert `.status_code` and `.detail` (a plain string).
- Tables, columns, constraints and the cached `Machine.section_assignment` relationship: see the assignment DAO spec, **Model facts** (`tests/unit/dao/machine_section_assignment.spec.md`). `FactorySection` needs `workspace_id`, `name`, `factory_id`; `is_active` defaults `True`, `is_deleted` `False`. `Factory` needs `workspace_id`, `name`, `abbreviation`; `is_deleted` defaults `False`. `Machine` needs `workspace_id`, `name`, `factory_id`.
- The section is read with the generic by-id lookup (`factory_section_dao.get_by_id_and_workspace`): id **and** workspace must match; soft-deleted sections **are** returned by it (factory section DAO spec, inherited methods).

**Notes for the test designer**
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `FactorySection`, `Machine` and `MachineSectionAssignment` rows directly (add + flush). The session runs with `autoflush=False`: flush before calling the manager.
- **Looking at rows:** check the table with a fresh `SELECT` (rows where `machine_id == M.id`), not through `machine.section_assignment`, which is cached (P2). Where a rule is about the cached relationship (`set_assignment` R12, `clear_for_section` R5), read `machine.factory_section_id` once before the call so it is loaded.
- **"Re-created" is observed through `id` and `created_by`, never `created_at`** (the transaction start time, identical for every row of one test).
- **Refusals (404 / 400)** happen before anything is written: the session stays usable, no savepoint needed. **Database errors** (foreign key, unique) abort the transaction: wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`.
- **BUG-910 (P1):** today the link is saved → deterministic → strict xfail. **BUG-909** (`set_assignment` R4): today new `id` and `created_by` = second user → strict xfail; use two different profiles. **BUG-907** (`clear_for_section` R3): 10 001 rows via bulk `insert(...)` of machines (`is_active=True, is_deleted=False, is_running=False`) and assignment rows; today 10 000 ids and 1 row left, as counts → strict xfail (the call takes about 7 s, one machine lookup per id). **BUG-906** (`clear_for_section` R7): the physical order on the test database is **not** deterministic — write the case to the intended order (assignment `id` ascending) and mark it **non-strict** xfail (`strict=False`); never weaken the assertion. Every other case compares the returned ids as a **set**.
- No test of the unreachable `machine is None` branch (`clear_for_section` R6).

## Not specified
- `MachineSectionAssignmentManager.__init__` — stores the assignment DAO and the factory section DAO, no logic
- `machine_section_assignment_manager` — module-level singleton, no logic

`clear_for_section` is on `docs/testing/dead-code-removal-checklist.md` ("remove together with the fix of BUG-908", entry already there) but is reachable today and therefore specified. The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks nothing else of this file as possibly unused (its former `get_for_machine` is already deleted). No legacy test outside `tests/unit/dao/` calls either method.

---

## `MachineSectionAssignmentManager.set_assignment(session, *, machine_id, factory_id, factory_section_id, workspace_id, user_id)`
**Shape:** create / delete (replace), with validation
**Persistence:** writes
**Visibility:** public (used by: `MachineManager.create_machine` when `factory_section_id` is not `None` ← `POST /machines/`; `MachineManager.update_machine` whenever `factory_section_id` is in the request, `null` included ← `PUT /machines/{id}/`)

**Purpose:** Put a machine into a section of its factory, move it to another one, or clear its section.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `machine_id` | int | machine whose link is set; not checked here (Q1) — only the database foreign key |
| `factory_id` | int | the factory the section must belong to (the callers pass the machine's factory); not checked to exist; ignored when clearing |
| `factory_section_id` | int \| `None` | `None` = clear the machine's section, no validation; any int (also `0`, negatives) = looked up and validated |
| `workspace_id` | int | caller's workspace: the section must belong to it; stored on the new link |
| `user_id` | int | stored as `created_by` of the new link (foreign key to `profiles.id`); `None` is stored as `NULL`; unused when clearing |

**Returns:** the new `MachineSectionAssignment` (flushed, not committed), or `None` when `factory_section_id` is `None`.

**Rules:**
- **R1.** Given a live section of the workspace whose `factory_id` equals `factory_id` and a machine without a link, the link is created and returned with `machine_id`, `factory_section_id`, `workspace_id` as given, `created_by = user_id`, `updated_by` / `updated_at` `None`; it is the machine's only link. Row details follow the assignment DAO `upsert_for_machine` R1.
- **R2.** Given such a section and a machine linked to a different section, the machine ends with exactly one link, pointing at the new section; it is a new row (new `id`, `created_by = user_id`) — assignment DAO `upsert_for_machine` R2 ✅ (DAO Q2).
- **R3.** Given `factory_section_id = None`, no section is looked up and nothing is validated (`factory_id` may be anything): a machine's link is deleted, `None` is returned; for a machine without a link — also an unknown machine id or an unknown `workspace_id` — `None` is returned and nothing is written. Details: assignment DAO `upsert_for_machine` R4, R7.
- **R4.** [BUG-909] (HR-9, inherited from the assignment DAO) Given the section the machine already has, nothing is written: the existing link is returned with the same `id`, `created_by` and `created_at`. *(Today: the link is deleted and a new one inserted — new `id`, `created_by` = the given user; still exactly one link.)* Fix in `app/dao/machine_section_assignment.py`.
- **R5.** No section with that id → `HTTPException` 404 `Factory section with ID <factory_section_id> not found`; nothing written, the machine's existing link unchanged. Also for `0` and negative ids (`Factory section with ID 0 not found`).
- **R6.** A section of another workspace → the same 404 with the same message (indistinguishable from not existing); nothing written.
- **R7.** A soft-deleted section of the workspace → 400 `Cannot assign a machine to a deleted factory section`; nothing written. This check comes before the factory check: a deleted section of another factory gets this message.
- **R8.** A live section of the workspace whose `factory_id` differs from `factory_id` → 400 `Factory section does not belong to this machine's factory`; nothing written. Also when `factory_id` names no factory at all.
- **R9.** [BUG-910] (P1) A live section of the workspace and of `factory_id`, whose factory is soft-deleted (`is_deleted = True`) → 400 `Cannot assign a machine to a deleted factory section`; nothing written, the machine's existing link unchanged. A section of another factory gets the R8 message first. A factory that is live but `is_active = False` is not refused. *(Today: the section's factory is not looked at; the link is saved and returned like for a live factory.)*
- **R9a.** A section with `is_active = False` (live, not deleted, of a live factory) is accepted like an active one: the link is saved. (Nothing in the application reads a section's `is_active`; factory section DAO Q1.)
- **R10.** ✅ (Q1) The machine is not looked at: given a valid section, the link is saved for a soft-deleted machine, for a machine whose own factory differs from `factory_id`, and for a machine of another workspace (stored with the given `workspace_id`). The callers do these checks (Follow-ups FU-2).
- **R11.** ✅ (Q1) An unknown `machine_id` with a valid section, or an unknown `user_id`, is not refused by the manager: the flush fails with `IntegrityError` (see Errors) and, inside a savepoint that is rolled back, the machine's previous link is back. A machine whose existing link has another `workspace_id` gets the unique violation of assignment DAO `upsert_for_machine` R7.
- **R12.** ✅ (P2) A `Machine` whose `section_assignment` was already loaded is not refreshed: its `factory_section_id` still gives the old value (after a set, a move or a clear) until the machine is expired or reloaded; then it gives the new value.
- **R13.** Changes are flushed, not committed: in the same session a fresh `SELECT` sees the new state; rolling back a savepoint around the call restores the previous link. Only the machine's own link is touched: other machines' links, the section, the factory and the machine rows are never written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no section with that id / section of another workspace | `HTTPException` 404 | `Factory section with ID <factory_section_id> not found` |
| section soft-deleted (checked before the factory) | `HTTPException` 400 | `Cannot assign a machine to a deleted factory section` |
| section belongs to another factory than `factory_id` | `HTTPException` 400 | `Factory section does not belong to this machine's factory` |
| [BUG-910] section's factory soft-deleted | `HTTPException` 400 | `Cannot assign a machine to a deleted factory section` *(today: no error)* |
| unknown `machine_id` (with a section) | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (`machine_section_assignments_machine_id_fkey`) | — (not asserted) |
| unknown `user_id` (with a section) | `IntegrityError` / `ForeignKeyViolation` (`machine_section_assignments_created_by_fkey`) | — |
| machine's existing link has another `workspace_id` | `IntegrityError` / `UniqueViolation` (`uq_machine_section_assignment_machine`) | — |

**Side effects:** at most one `machine_section_assignments` row deleted and at most one inserted, flushed (none on a refusal; intended none when the section is unchanged — BUG-909). No commit. No other table written.

---

## `MachineSectionAssignmentManager.clear_for_section(session, *, factory_section_id, workspace_id)`
**Shape:** delete (bulk)
**Persistence:** writes
**Visibility:** public (used by: `FactorySectionManager.delete_factory_section` ← `DELETE /factory-sections/{id}/`, right after the section is soft-deleted. That call is BUG-908; once it is fixed this method has no caller and is removed — dead-code list, "remove together with the fix of BUG-908".)

**Purpose:** Unassign every machine of a section, refresh those machines in memory, and say which machines they were.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `factory_section_id` | int | section whose links are removed; not validated (any integer; the section's state does not matter) |
| `workspace_id` | int | only links with this `workspace_id` are removed |

**Returns:** a `list` of the `machine_id`s whose links were removed (one entry per removed link), possibly empty.

**Rules:**
- **R1.** Every link of the section in the workspace is deleted (a real DELETE) and its machine id is returned — also links of soft-deleted machines, and whether the section is live or soft-deleted. Links to other sections, and links of another workspace pointing at the same section id, are untouched and not returned. Details: assignment DAO `clear_for_section` R1–R3.
- **R2.** An unknown section id, or a section without links in the workspace, returns `[]` and writes nothing.
- **R3.** [BUG-907] (inherited from the assignment DAO) All links of the section are removed however many there are: given 10 001 links, 10 001 machine ids are returned and no link is left. *(Today: 10 000 ids, 1 link left; a second call removes it.)* Goes away with the method (BUG-908).
- **R4.** The section row, the machine rows and the factory row are never written.
- **R5.** Every machine whose link was removed reads `factory_section_id = None` right after the call, also when its section had been read before the call (the manager refreshes it — unlike `set_assignment`, R12 there). Other attributes of such a machine are not reset: a name changed in memory before the call keeps its new value.
- **R6.** Machines not yet loaded in the session are loaded and refreshed too; every returned id belongs to an existing machine. (The code skips an id whose machine cannot be found; that cannot happen — a link's machine always exists, the foreign key deletes links with their machine. Not tested.)
- **R7.** [BUG-906] (HR-6, inherited) The ids are in the order of the links' `id`, ascending. *(Today: unspecified.)* Every other case compares them as a set.
- **R8.** Changes are flushed, not committed: rolling back a savepoint around the call brings every link back.

**Errors:** none raised by the method itself.

**Side effects:** up to 10 000 (intended: all) `machine_section_assignments` rows deleted and flushed; the affected machines' cached `section_assignment` expired; no commit; no other table written.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 15–17 | `__init__` wiring | Not specified |
| 19–22 | keyword-only parameters | Facts for the test designer |
| 26 | `factory_section_id is not None` → validate / `None` → skip validation (`0` and negatives are validated) | `set_assignment` R3, R5 |
| 27–29 / `dao/base.py` 187–195 | raw lookup by id **and** workspace; no `is_deleted` filter | `set_assignment` R5, R6, R7 |
| 30–34 | `not section` → 404 (missing / other workspace) | `set_assignment` R5, R6 |
| 35–39 | `section.is_deleted` → 400 (before the factory check) | `set_assignment` R7 |
| 40–44 | `section.factory_id != factory_id` → 400 | `set_assignment` R8 |
| — (no check) | section's factory deleted (BUG-910); section `is_active`; machine existence / workspace / deleted / factory | `set_assignment` R9, R9a, R10, R11 |
| 46–49 / `dao/machine_section_assignment.py` 43–55 | upsert: existing link deleted (also same section — BUG-909); `None` → return `None`; insert, flush; FK / unique errors; machine not expired | `set_assignment` R1, R2, R3, R4, R11, R12, R13 |
| 57–59 / `dao/machine_section_assignment.py` 64–69 | DAO clear: `limit=10000` cap (BUG-907), no order (BUG-906), delete each, flush | `clear_for_section` R1, R2, R3, R4, R7, R8 |
| 60 | loop over ids: empty / one / many | `clear_for_section` R2, R5, R6 |
| 61 | `session.get` loads the machine (identity map or database) | `clear_for_section` R6 |
| 62 | `machine is not None` → expire / `None` → skip (unreachable) | `clear_for_section` R5, R6 |
| 63 | expire only `section_assignment` | `clear_for_section` R5 |
| 64 | return ids, no commit | `clear_for_section` R1, R8 |
| 67 | module singleton | Not specified |
