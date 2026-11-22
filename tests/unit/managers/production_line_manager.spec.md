# Spec — `app/managers/production_line_manager.py`

> **Status:** PAUSED. Production is deferred until the revamp (owner 2026-11-19); see docs/future/production-revamp.md.
> **Source commit:** e48a092

> **Review round 2026-11-19 (describe, under the reviewer's delegation of 2026-11-19).** **Delegated:** every P and D item below was decided by Claude under the reviewer's delegation (2026-11-19). None of them is the owner's own answer. The house-rule lines stand. **Owner:** O1 touches stock: it decides which factory a line's batches take materials from and post finished goods into. It is written as an owner question with a recommended answer. **Bug IDs are provisional** (BUG-2852 … BUG-2861 of the block 2852–2871). The parent merges them into `docs/testing/bugs.md`.

> **Below this manager.** `tests/unit/dao/production_line.spec.md` (APPROVED) is not restated. It covers the four reads, including ordering (BUG-100, BUG-1310, BUG-1311), lines of a soft-deleted factory in the factory and active lists (BUG-1312), and its Q1 (✅ intended): `is_active` is a switch, not a deleted state, and an inactive line is a normal, visible row. The DAO spec's **FU-1 (a)–(f)** is the checklist for this manager, and each item is answered below. The factory DAO's FU-3, the factory manager's FU-5 and the machine manager's FU-10 are answered here too. Inherited `BaseDAO.get` / `create` / `update` follow `tests/unit/dao/base.spec.md`: `get` is a raw by-id read in any workspace, deleted or not; `create` builds the row from the dict and flushes; `update` sets every key of the dict that is an attribute of the row and flushes.
>
> **Standing decisions applied here (not asked again):** things of a soft-deleted parent are hidden (BUG-882 / BUG-966). A soft-deleted parent is refused as "not found" on create (BUG-715). HR-16: a row of another workspace gets the same answer as a missing id (BUG-1021, already logged for this manager). A refused delete lists what blocks it (BUG-948). It does not apply here because the delete is a deactivate, see D2.
>
> **Cost rules (owner, cited, not re-asked):** OQ-50 (production output cost stays manual, revisit after launch), OQ-51 / BUG-2793 (`make_sellable`) and BUG-2811 (a new bucket records `avg_cost_before` NULL) do not reach this manager: lines carry no cost, quantity or money. **Projects:** none touched.
>
> **Read, not run:** this file in full; `app/dao/production_line.py`; `app/dao/base.py`; `app/dao/factory.py` and `app/dao/machine.py` (neither overrides `get`); `app/models/production_line.py`, `factory.py`, `machine.py`; `app/schemas/production_line.py`; `app/services/production_line_service.py`; `app/api/v1/endpoints/production_lines.py`; `ProductionBatchManager.create_batch` (:80–86), `start_batch` (:266–271), `complete_batch` (:396–401), `post_outputs_to_finished_goods` (:705–710); `MachineManager.update_machine` (:132–149). The DAO spec's verified facts (2026-11-02, `marker_test`, rolled back) are relied on: `factory_id` wins over `active_only`; `delete_production_line` leaves `updated_by` `None`; `update_production_line` drops `machine_id: null`; a whitespace-only name passes the schema; two same-named lines are both saved.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-6 | The plain line list has no sort order | bug (BUG-2852) | house rule |
| HR-9 | An edit that changes nothing still stamps `updated_by` | bug (BUG-2859) | house rule |
| P1 | The plain line list shows lines of a deleted factory | bug (BUG-2853) | Claude, delegated (BUG-1312 precedent) |
| P2 | Opening a line of a deleted factory by id returns it | bug (BUG-2855) | Claude, delegated (BUG-966 precedent) |
| P3 | A line can be created in a deleted factory | bug (BUG-2856) | Claude, delegated (BUG-715 precedent) |
| P4 | A deleted machine can be attached to a line | bug (BUG-2857) | Claude, delegated (BUG-715 / BUG-963 precedent) |
| P5 | An edit cannot detach the machine or clear the description | bug (BUG-2858) | Claude, delegated (BUG-713 precedent) |
| D1 | "Active only" is ignored when a factory is chosen | bug (BUG-2854) | Claude, delegated |
| D2 | Deleting a line only switches it off, records no one, and is allowed with open batches | bug for "records no one" (BUG-2860); switching off with open batches is intended | Claude, delegated |
| D3 | Missing factory or machine on create answers 422; on update it answers 404 | bug (BUG-2861, service) | Claude, delegated |
| D4 | Editing or switching off a line of a deleted factory still works | intended | Claude, delegated |
| O1 | A machine moved to another factory leaves its line behind, and the line can then not be re-saved with its machine | _pending_ (owner) | owner |

Already logged, no new ID: BUG-1021 (another workspace's factory, machine or line answered differently from a missing id; `create` R3, R6; `update` R2, R6; `delete` R2), BUG-1313 (blank or untrimmed names, a schema fix; `create` R11), BUG-1310 / BUG-1311 / BUG-1312 (order of the factory and active lists, and their lines of a deleted factory, in the DAO), BUG-100 (`id` order of the raw list).

### House-rule violations — applied automatically

- **HR-6** `get_production_lines` R6: with neither `factory_id` nor `active_only`, the list (`GET /production-lines/`) has no `ORDER BY`. BUG-100 gives the raw DAO list `id` order only; the display order is the manager's job. Intended: `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`, as BUG-1310 / BUG-1311 for the two filtered lists.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2852 (pattern `unordered-pagination`). Answers DAO FU-1 (a).
- **HR-9** `update_production_line` R8: `updated_by` is written on every call that passes validation, even `{}`, `{"name": null}`, or values equal to the stored ones. Intended: `updated_by` is written only when at least one field actually changes value. Otherwise the row is returned untouched.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** BUG-2859 (pattern `audit-stamp-on-noop`). Answers DAO FU-1 (f).

Checked and **not** a new line here: **HR-1**: BUG-1313 (existing; schema). **HR-2**: line names are not meant to be unique (DAO spec, checked): two lines named "Press" in one factory are both saved. **HR-3, HR-8**: no grouping text, no `LIKE`. **HR-4**: lines have no `is_deleted`. Inactive is a normal state (DAO Q1 ✅). Deleted *parents* are handled by P1–P4. **HR-5**: the P1 and D1 fixes must filter inside the query, before paging. **HR-7**: `GET /production-lines/` already requires `1 <= limit <= 1000` and `skip >= 0`. **HR-10**: deactivating, renaming and attaching a machine move no money or stock and cause no side effects; no lock is needed. **HR-11 … HR-14**: no externals. **HR-15**: no money. **HR-16**: factory, machine and line are compared with the workspace. Only the wording is wrong (BUG-1021).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-19)

### P1. The plain line list shows lines of a deleted factory — 🐞 BUG-2853
**Background:** Deleting a factory is a soft delete: the factory row is flagged `is_deleted` and its lines stay as they were. BUG-1312 already hides such lines in the "lines of one factory" and "active lines" lists. The plain list (no filter) uses a different read that BUG-1312 does not cover.
**What happens today:** `GET /production-lines/` with no filter returns every line of the workspace, including the lines of a deleted factory.
**Example:** Factory 3 "Old Plant" is deleted. With `?active_only=true` its "Line A" disappears (after BUG-1312). Without the filter, "Line A" is still listed and takes a place on the page.
**Rules affected:** `get_production_lines` R5
**Answer:** bug — per BUG-1312 precedent: a line whose factory has `is_deleted = True` is not returned and takes no place in the page, filtered inside the query. The line is untouched and comes back unchanged with the factory. An inactive-but-live factory hides nothing.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2853 (pattern `join-ignores-soft-deleted`). Answers DAO FU-1 (b).

### P2. A line of a deleted factory can still be opened by id — 🐞 BUG-2855
**Background:** BUG-966 ruled that a machine of a deleted factory answers 404 when opened by id, while `include_deleted=True` still returns it. The line lists hide such lines (BUG-1312, P1).
**What happens today:** `get_production_line` reads the line only: 200.
**Example:** Factory 3 is deleted. "Line A" is in no list, but `GET /production-lines/12/` still opens it.
**Rules affected:** `get_production_line` R3
**Answer:** bug — per BUG-966 precedent: `None` by default (the service then answers 404 `Production line with ID {line_id} not found`). A new `include_deleted=True` parameter returns it, reachable from the API. An inactive-but-live factory hides nothing. A line of a soft-deleted machine is returned, because the machine link is optional (DAO spec).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2855 (pattern `join-ignores-soft-deleted`). *(requires new parameter `include_deleted`, passed by the service and the endpoint)*. The batch and formula managers read lines through the DAO, not through this method, so nothing changes for a running batch.

### P3. A line can be created in a deleted factory — 🐞 BUG-2856
**Background:** The factory is looked up with the raw `factory_dao.get`, which returns deleted factories. BUG-715 ruled for stock rows, and BUG-2780 for products, that a soft-deleted factory counts as not found on create.
**What happens today:** `POST /production-lines/` with a deleted factory answers 201. After P1 / BUG-1312 the line is then hidden at once.
**Example:** A user picks "Old Plant" from a stale form and creates "Line B". The line is created and then appears in no list.
**Rules affected:** `create_production_line` R4
**Answer:** bug — per BUG-715 precedent: `ValueError("Factory {factory_id} not found")`, nothing written. An inactive-but-live factory is accepted.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2856 (pattern `unvalidated-foreign-key-reference`). Answers factory DAO FU-3 and factory manager FU-5.

### P4. A deleted machine can be attached to a line — 🐞 BUG-2857
**Background:** The machine is looked up with the raw `machine_dao.get`, which returns deleted machines. A deleted machine is in no machine list.
**What happens today:** `create_production_line` and `update_production_line` accept a soft-deleted machine of the right factory and store its id.
**Example:** "Press 2" was deleted last week. A user attaches it to "Line A" by its id and gets 200. The line now shows a machine that exists nowhere else.
**Rules affected:** `create_production_line` R7; `update_production_line` R6 (c)
**Answer:** bug — per BUG-715 / BUG-963 precedent: a machine with `is_deleted = True` gets `ValueError("Machine {machine_id} not found")`, nothing written. An inactive-but-live machine is accepted. A line already attached to a machine that was later deleted keeps it; only *setting* a deleted machine is refused.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2857 (pattern `unvalidated-foreign-key-reference`).

### P5. An edit cannot detach the machine or clear the description — 🐞 BUG-2858
**Background:** `update_production_line` drops every field sent as `null` (`exclude_none`). BUG-713 ruled for stock rows that an explicit `null` clears an optional field. The model says a line may be "standalone" (no machine).
**What happens today:** `{"machine_id": null}` or `{"description": null}` → 200, old value kept (verified at the DAO).
**Example:** "Line A" is moved off "Press 2" to become a standalone line. The user clears the machine and saves, but the line still shows "Press 2".
**Rules affected:** `update_production_line` R5
**Answer:** bug — per BUG-713 precedent: an explicit `null` for `machine_id` detaches the machine (`machine_id` NULL) and for `description` clears it. `null` for `name` or `is_active` → 422 (schema). Omitted fields stay unchanged.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2858 (pattern `exclude-none-blocks-clear`). Answers DAO FU-1 (e). The fix is in the manager (`exclude_unset` only) and in `ProductionLineUpdate` (`name`, `is_active` not nullable).

### New questions (decided by Claude under the reviewer's delegation, 2026-11-19, except O1)

### D1. "Active only" is ignored when a factory is chosen — 🐞 BUG-2854
**Background:** The list takes two filters, `factory_id` and `active_only`. The code picks one read: when a factory is given, the active flag is not looked at.
**What happens today:** `GET /production-lines/?factory_id=1&active_only=true` also returns the factory's inactive lines (verified at the DAO).
**Example:** Factory 1 has "Line A" (active) and "Line C" (switched off). A batch form asking for "active lines of Factory 1" offers both, and choosing "Line C" then fails with "Production line … is not active".
**Rules affected:** `get_production_lines` R2
**Answer:** bug — both filters apply together: only active lines of that factory, inside the query, ordered as BUG-1310.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2854 (pattern `silently-ignored-input`). Answers DAO FU-1 (c). The fix needs a DAO read with both filters.

### D2. Deleting a line only switches it off, and records no one — 🐞 BUG-2860 (stamp); open batches intended
**Background:** Production lines have no deleted state. `DELETE /production-lines/{id}/` sets `is_active = False`, the same as `PUT` with `is_active: false`, and the DAO review ruled that state a normal, visible switch (DAO Q1 ✅). Only *creating* a batch refuses an inactive line. Starting and completing a batch read the line without looking at `is_active`, so a batch already on the line can still finish.
**What happens today:** (a) the delete writes no `updated_by` (verified: `None`); the method does not even receive the user. (b) A line with `draft` or `in_progress` batches can be switched off; those batches can still be started and completed, and no stock is touched by switching off.
**Example:** (a) "Line A" is switched off through `DELETE`; nobody can tell who did it, while the same change through `PUT` records the user. (b) "Line A" has batch B-0042 in progress. The line is switched off; B-0042 still completes and posts its finished goods; no new batch can be created on "Line A".
**Rules affected:** `delete_production_line` R3, R4, R5
**Answer:** (a) bug — the deactivate stamps `updated_by` with the acting user when `is_active` actually changes (HR-9: an already inactive line is left untouched). (b) intended — a switch, not a delete; work in progress may finish; no blocker list.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2860 (pattern `audit-stamp-missing-on-change`) *(requires new parameter `user_id`, passed by `ProductionLineService.delete_production_line` from the endpoint's `current_user`, which the endpoint already has)*. (b) no bug; whether *starting* a draft batch on an inactive line should be refused is for the batch manager review (FU-1). Answers DAO FU-1 (d).

### D3. A missing factory or machine answers 422 on create, 404 on update — 🐞 BUG-2861 (service)
**Background:** The manager raises a plain `ValueError` for every refusal. `ProductionLineService` translates it, differently per method: `create` turns every `ValueError` into 422 `BusinessRuleError`; `update` gives 404 when the text contains "not found", else 422; `delete` gives 404 always.
**What happens today:** `POST` with an unknown `factory_id` or `machine_id` → 422 "Factory 99 not found". `PUT` with an unknown `machine_id` → 404 "Machine 99 not found".
**Example:** The frontend handles "not found" as 404 everywhere else. A stale factory id on the create form shows up as a validation error instead.
**Rules affected:** none of this manager (the messages stay as specified); service `create_production_line`
**Answer:** bug — on create, a `… not found` refusal answers 404 `NotFoundError` with the same text, as on update. "Machine … does not belong to factory …" stays 422.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19): 🐞 BUG-2861 (pattern `lossy-error-mapping`), fix in `app/services/production_line_service.py`. With BUG-1021 fixed, another workspace's factory or machine also answers 404.

### D4. Editing or switching off a line of a deleted factory still works — ✅ intended
**Background:** After P1 / P2 such a line is hidden from lists and from opening by id. `update_production_line` and `delete_production_line` keep their own raw read of the line.
**What happens today:** `PUT` / `DELETE` on a line of a deleted factory succeed.
**Example:** Someone with an old link renames "Line A" of the deleted "Old Plant". The rename is saved. Nobody sees it until the factory is restored, and then the line comes back renamed.
**Rules affected:** `update_production_line` R3; `delete_production_line` R6
**Answer:** intended — harmless (no stock, no money), the same choice as `product_manager` P1 (update and delete keep their raw read).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-19). Rules unchanged.

### Owner question

### O1. A machine moved to another factory leaves its production line behind — _pending (owner)_
**Background:** A production line belongs to one factory and may be attached to one machine. Production batches take their materials from, and put their finished goods into, **the line's factory**. The machine can be moved to another factory (`PUT /machines/{id}/` with a new factory). When that happens nothing changes on the line: it stays in the old factory, still attached to the machine that is now elsewhere. The owner already decided that open work orders follow a moved machine (machine manager O4, BUG-975); production lines were not part of that answer (machine manager FU-10).
**What happens today:** The line keeps its old factory and still names the moved machine. Its batches keep using the old factory's stock. When anyone edits the line and the form sends the machine again, the edit is refused: "Machine 7 does not belong to factory 1".
**Example:** "Line A" in Dhaka Plant is attached to "Extruder 7". Extruder 7 is moved to Gazipur Plant. "Line A" still says Dhaka Plant and Extruder 7. Its next batch takes resin from Dhaka stock and puts finished pipes into Dhaka stock. Renaming "Line A" from the edit form then fails, because the form re-sends Extruder 7.
**Rules affected:** `update_production_line` R6 (d) today; the fix lives in `MachineManager.update_machine`. No rule of this manager changes under any option.
**Options (for the owner, plain language):**
- **A. The line stays and lets go of the machine (recommended).** The line is a place in the factory: it stays in Dhaka Plant, and its link to Extruder 7 is removed when the machine moves. Its batches keep using Dhaka stock, exactly as today, so no stock moves between factories by surprise. The line can be attached to another machine afterwards.
- **B. The line moves with the machine.** "Line A" moves to Gazipur Plant together with Extruder 7, as open work orders already do. From then on its batches take materials from and post finished goods into Gazipur stock. A batch already in progress started with Dhaka materials and will put its finished goods into Gazipur, so stock is split between two factories for that one batch.
- **C. The machine cannot move while a line is attached.** Moving Extruder 7 is refused with a message naming "Line A". The user must detach the machine from the line (or switch the line to another machine) first, then move it. Nothing changes by surprise, but it is one more step for the user.
- **D. Keep today's behaviour.** The line stays in Dhaka Plant still pointing at a machine in Gazipur, and editing it with the machine re-sent keeps failing until someone detaches the machine.

**Recommended answer:** A. It keeps every batch's stock in the factory where it started, needs no extra step from the user, and matches "a line is a place in a factory; a machine is optional" (model comment, DAO spec).
**Answer:** _pending_

## Overview
`ProductionLineManager` owns production lines, the physical lines of a factory where production batches run. Each line belongs to one factory and may be attached to one machine of that factory. It is called only by `ProductionLineService` behind `/production-lines/`. The service commits or rolls back, then re-reads the row (transaction contract TC1–TC6, `tests/unit/services/base_service.spec.md`; tested in the service spec). It protects workspace isolation (factory, machine and line must be in the caller's workspace) and one invariant: a line's machine is in the line's factory. The manager never commits; the DAO flushes. The line's factory cannot be changed after creation. The batch manager reads lines through the DAO directly, not through this manager.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none. The table has no timestamps, so `utcnow` is not involved.
**Integration-only behavior:** none.

**Model and schema facts** (as the DAO spec): table `production_lines`, columns `id`, `workspace_id` (NOT NULL), `factory_id` (NOT NULL, FK RESTRICT), `machine_id` (nullable, FK `machines.id` ON DELETE SET NULL), `name` String(200) NOT NULL, `description` Text, `is_active` (Python default `True`), `created_by` / `updated_by` (FK `profiles.id`, nullable). No `is_deleted`, no timestamps, no unique constraint.
- `ProductionLineCreate`: `factory_id: int` (required), `machine_id: int | None = None`, `name: str` (1–200), `description: str | None = None`, `is_active: bool = True`. No `workspace_id` and no `created_by` (the manager adds them).
- `ProductionLineUpdate`: `machine_id`, `name` (1–200 when given), `description`, `is_active`, all optional and default `None`. **No `factory_id`**: a sent `factory_id` is ignored (Pydantic's default `extra = "ignore"`).
- `Factory` and `Machine` soft delete = `is_deleted = True` (both also have `is_active`). `Machine.factory_id` is NOT NULL.
- Service error mapping (for orientation; tested in the service spec): create: any `ValueError` → 422 `BusinessRuleError(str(e))` (BUG-2861). Update: text contains `not found` → 404 `NotFoundError`, else 422. Delete: any `ValueError` → 404. Get: `None` → 404 `Production line with ID {line_id} not found`.

**Notes for the test designer**
- `from app.managers.production_line_manager import production_line_manager`. Call with keywords as the service does: `create_production_line(session, line_data, workspace_id, user_id)`, `update_production_line(session, line_id, line_data, workspace_id, user_id)`, `get_production_line(session, line_id, workspace_id)`, `get_production_lines(session, workspace_id, factory_id=None, active_only=False, skip=0, limit=100)`, `delete_production_line(session, line_id, workspace_id)`.
- Build rows as in the DAO spec Notes: `make_workspace(db)` and a `Profile` from `tests/unit/factories.py`; then `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)`, `ProductionLine(workspace_id, factory_id, name)`, added and flushed. The session runs with `autoflush=False`.
- "Nothing written" = re-select the `production_lines` rows (count and values) after the `ValueError`.
- Order cases (BUG-2852): write to the intended order, **non-strict** xfail, with a forced sequential scan as in the DAO spec Notes. Every other list case compares **sets** of ids.
- The "machine moved" state of O1 is built directly: a line on factory F1 with `machine_id` of a machine whose `factory_id` is F2.

## Not specified
- `ProductionLineManager.__init__`: wires the model and DAO, no logic.
- `production_line_manager`: module singleton.

---

## `ProductionLineManager.create_production_line(session, line_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ProductionLineService.create_production_line` ← `POST /production-lines/`)

**Purpose:** Add a production line to a factory of the workspace, optionally attached to one of that factory's machines.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `line_data` | `ProductionLineCreate` | see Overview; name length by the schema |
| `workspace_id` | int | the caller's workspace; becomes the row's `workspace_id` |
| `user_id` | int | becomes `created_by`; not checked here (FK at flush) |

**Returns:** the new `ProductionLine`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** Given a live factory of the workspace and no machine, a row is created with `workspace_id` = the argument, `factory_id`, `name`, `description` and `is_active` as sent (`is_active` defaults to `True`), `machine_id` NULL, `created_by` = `user_id`, `updated_by` NULL.
- **R2.** An unknown `factory_id` → `ValueError("Factory {factory_id} not found")`, nothing written.
- **R3.** [BUG-1021] A factory of another workspace gets exactly the answer of a missing one: `ValueError("Factory {factory_id} not found")`, nothing written. *(Today: `Factory {factory_id} does not belong to workspace {workspace_id}`.)*
- **R4.** [BUG-2856] A factory with `is_deleted = True` → `ValueError("Factory {factory_id} not found")`, nothing written. A factory with `is_active = False` and `is_deleted = False` is accepted. *(Today: the deleted factory is accepted and the line created.)*
- **R5.** With `machine_id` given (any value that is not `None`, `0` included), the machine must exist: an unknown id → `ValueError("Machine {machine_id} not found")`, nothing written.
- **R6.** [BUG-1021] A machine of another workspace → `ValueError("Machine {machine_id} not found")`, nothing written. *(Today: `Machine {machine_id} does not belong to workspace {workspace_id}`.)*
- **R7.** [BUG-2857] A machine with `is_deleted = True` → `ValueError("Machine {machine_id} not found")`, nothing written. A machine with `is_active = False` (not deleted) is accepted, whatever `is_running` is. *(Today: the deleted machine is accepted.)*
- **R8.** A machine of the workspace that belongs to another factory → `ValueError("Machine {machine_id} does not belong to factory {factory_id}")`, nothing written.
- **R9.** The factory is checked before the machine: an unknown factory together with an unknown machine gives the factory's message.
- **R10.** A valid machine of the same factory is stored as `machine_id`.
- **R11.** Names: the schema enforces 1–200 characters (422 before the manager). [BUG-1313] A whitespace-only name is rejected by the schema with 422, and a name is stored trimmed (`" Line A "` → `"Line A"`). *(Today: both pass unchanged; schema fix.)* A name already used by another line, even in the same factory, is accepted.
- **R12.** An unknown `user_id` makes the flush fail with `IntegrityError` (foreign key, pgcode `23503`).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| factory unknown, of another workspace [BUG-1021], or deleted [BUG-2856] | `ValueError` | `Factory {factory_id} not found` |
| machine unknown, of another workspace [BUG-1021], or deleted [BUG-2857] | `ValueError` | `Machine {machine_id} not found` |
| machine of another factory | `ValueError` | `Machine {machine_id} does not belong to factory {factory_id}` |
| unknown `user_id` | `sqlalchemy.exc.IntegrityError` (23503) | — |

**Side effects:** one `production_lines` row inserted and flushed. No other table touched.

---

## `ProductionLineManager.update_production_line(session, line_id, line_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ProductionLineService.update_production_line` ← `PUT /production-lines/{line_id}/`)

**Purpose:** Rename a line, change its description, switch it on or off, or attach it to another machine of its factory.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `line_id` | int | the line to change |
| `line_data` | `ProductionLineUpdate` | see Overview; no `factory_id` |
| `workspace_id` | int | the caller's workspace |
| `user_id` | int | becomes `updated_by` |

**Returns:** the same `ProductionLine`, flushed, not committed.

**Rules:**
- **R1.** An unknown `line_id` → `ValueError("Production line {line_id} not found")`, nothing written.
- **R2.** [BUG-1021] A line of another workspace → `ValueError("Production line {line_id} not found")`, nothing written. *(Today: `Production line {line_id} does not belong to workspace {workspace_id}`.)*
- **R3.** ✅ (D4) The line's own state and its factory's are not looked at: an inactive line, and a line of a soft-deleted factory, can be updated.
- **R4.** Every field present in the request with a non-null value is written: `name`, `description`, `machine_id`, `is_active`. Omitted fields stay as they are. `is_active: true` switches an inactive line back on; `is_active: false` switches it off (same state as `delete_production_line`).
- **R5.** [BUG-2858] An explicit `null` for `machine_id` detaches the machine (`machine_id` NULL, no machine check), and an explicit `null` for `description` clears it. `null` for `name` or `is_active` is rejected by the schema with 422. *(Today: every `null` is dropped and the old value is kept.)*
- **R6.** When `machine_id` is sent with a value, it is checked before anything is written, even when it equals the line's current machine: (a) an unknown id → `ValueError("Machine {machine_id} not found")`; (b) [BUG-1021] a machine of another workspace → the same message *(today: `Machine {machine_id} does not belong to workspace {workspace_id}`)*; (c) [BUG-2857] a machine with `is_deleted = True` → the same message *(today: accepted)*; (d) a machine whose `factory_id` differs from the **line's** factory → `ValueError("Machine {machine_id} does not belong to factory {line.factory_id}")`. This includes the line's own machine after it was moved to another factory (*pending O1*: under every option of O1 this manager's rule stays as written). In each case nothing is written.
- **R7.** The line's factory cannot be changed: a `factory_id` in the request is ignored, and the line keeps its factory with no error.
- **R8.** [BUG-2859] (HR-9) `updated_by` = `user_id` is written only when at least one field actually changes value. For `{}`, for only-`null` fields (`name`, `is_active`), or for values equal to the stored ones, the row is returned with no field changed. *(Today: `updated_by` is written on every call that passes R1–R6.)*
- **R9.** The checks run in the order R1, R2, R6. A missing line together with an unknown machine gives the line's message.
- **R10.** When `updated_by` is written with an unknown `user_id`, the flush fails with `IntegrityError` (23503).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| line unknown, or of another workspace [BUG-1021] | `ValueError` | `Production line {line_id} not found` |
| machine unknown, of another workspace [BUG-1021], or deleted [BUG-2857] | `ValueError` | `Machine {machine_id} not found` |
| machine not in the line's factory | `ValueError` | `Machine {machine_id} does not belong to factory {factory_id of the line}` |
| unknown `user_id` | `IntegrityError` (23503) | — |

**Side effects:** the line's changed fields and `updated_by` are set and flushed. No other table touched.

---

## `ProductionLineManager.get_production_line(session, line_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ProductionLineService.get_production_line` ← `GET /production-lines/{line_id}/`)

**Purpose:** One line of the workspace by id.

**Returns:** the `ProductionLine`, or `None`.

**Rules:**
- **R1.** A line of the workspace is returned, active or inactive.
- **R2.** An unknown id, or a line of another workspace, returns `None` (the two cannot be told apart).
- **R3.** [BUG-2855] A line whose factory has `is_deleted = True` returns `None` by default. With a new `include_deleted=True` it is returned. A factory with `is_active = False` hides nothing. A line attached to a soft-deleted machine is returned. *(Today: returned. Requires new parameter `include_deleted`.)*

**Errors:** none. **Side effects:** none.

---

## `ProductionLineManager.get_production_lines(session, workspace_id, factory_id=None, active_only=False, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionLineService.get_production_lines` ← `GET /production-lines/`, which passes all four and bounds `skip >= 0`, `1 <= limit <= 1000`)

**Purpose:** A page of the workspace's lines, optionally only one factory's and/or only active ones.

**Returns:** a `list` of `ProductionLine` (possibly empty).

**Rules:**
- **R1.** With `factory_id` given (any value that is not `None`, `0` included), only that factory's lines of the workspace are returned. Order, paging and the hiding of a deleted factory's lines follow `production_line.spec` `get_by_factory` R1–R7 (BUG-1310, BUG-1312). A factory of another workspace, or `factory_id=0`, gives `[]`.
- **R2.** [BUG-2854] With `factory_id` and `active_only=True`, only the **active** lines of that factory are returned, filtered inside the query before paging, in `get_by_factory` R4's order. *(Today: `active_only` is ignored and inactive lines are returned.)* With `active_only=False`, active and inactive lines are returned.
- **R3.** Without `factory_id` and with `active_only=True`, the active lines of the workspace are returned: `production_line.spec` `get_active_by_workspace` R1–R6 (BUG-1311, BUG-1312).
- **R4.** With neither filter, every line of the workspace is returned, active and inactive, including lines attached to a soft-deleted machine. Lines of another workspace never appear.
- **R5.** [BUG-2853] With neither filter, a line whose factory has `is_deleted = True` is not returned and takes no place in the page, inside the query. The line is untouched and is listed again once the factory is no longer deleted. An inactive-but-live factory hides nothing. *(Today: listed.)*
- **R6.** [BUG-2852] (HR-6) With neither filter, lines are ordered by `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`: "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu". *(Today: no order.)*
- **R7.** At most `limit` lines after skipping `skip`; with the defaults at most 100 (given 101 lines, exactly 100). `skip` past the end gives `[]`. Consecutive pages share no line and miss none (relies on R6 / the DAO orders).

**Errors:** a negative `skip` / `limit` (not reachable from the API) fails in Postgres as in the DAO spec. **Side effects:** none.

---

## `ProductionLineManager.delete_production_line(session, line_id, workspace_id)`
**Shape:** state-transition (deactivate; called "soft delete" in the code)
**Persistence:** writes
**Visibility:** public (used by: `ProductionLineService.delete_production_line` ← `DELETE /production-lines/{line_id}/`, 204)

**Purpose:** Switch a line off so no new batch can be created on it.

**Returns:** the same `ProductionLine`, flushed, not committed. The service returns nothing.

**Rules:**
- **R1.** An unknown `line_id` → `ValueError("Production line {line_id} not found")`, nothing written.
- **R2.** [BUG-1021] A line of another workspace → `ValueError("Production line {line_id} not found")`, nothing written. *(Today: `Production line {line_id} does not belong to workspace {workspace_id}`.)*
- **R3.** ✅ (D2 b) An active line gets `is_active = False`. The row stays, every other column is unchanged, and the line stays visible in the plain list and by id. Its batches (any status) and the formula stages that name it are not touched, and nothing is refused because of them.
- **R4.** [BUG-2860] When `is_active` changes, `updated_by` = the acting user. *(Today: `updated_by` is not written. Requires new parameter `user_id`, passed by the service from the endpoint's `current_user`.)*
- **R5.** An already inactive line succeeds with no error. Nothing changes, and after BUG-2860 no stamp either (HR-9).
- **R6.** ✅ (D4) A line of a soft-deleted factory is switched off like any other.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| line unknown, or of another workspace [BUG-1021] | `ValueError` | `Production line {line_id} not found` |

**Side effects:** `is_active` (and, after BUG-2860, `updated_by`) set and flushed. No other table touched.

---

## Bugs found while reading (provisional IDs, for the parent to merge into `docs/testing/bugs.md`)
| ID | Pattern | Module | Title | Today | Intended | Spec |
|---|---|---|---|---|---|---|
| BUG-2852 | `unordered-pagination` | `app/managers/production_line_manager.py` (`get_production_lines`, no filter; `GET /production-lines/`) | The plain production line list has no sort order | No `ORDER BY` (BUG-100 gives `id` only) | HR-6: `name` case-insensitive, then `id`, before paging | HR-6 line |
| BUG-2853 | `join-ignores-soft-deleted` | same, no filter | The plain line list shows lines of a deleted factory | Listed and paged | Hidden inside the query; back unchanged with the factory; inactive factory hides nothing (BUG-1312 precedent) | P1 |
| BUG-2854 | `silently-ignored-input` | same, `factory_id` + `active_only` | "Active only" ignored when a factory is chosen | Inactive lines of the factory returned | Both filters apply, inside the query, BUG-1310 order | D1 |
| BUG-2855 | `join-ignores-soft-deleted` | `get_production_line`; `GET /production-lines/{id}/` | A line of a deleted factory still opens by id | 200 | `None` (404) by default; new `include_deleted=True` returns it (BUG-966 precedent) | P2 |
| BUG-2856 | `unvalidated-foreign-key-reference` | `create_production_line` | A line can be created in a deleted factory | 201, line hidden at once | `Factory {id} not found`, nothing written; inactive factory accepted (BUG-715 precedent) | P3 |
| BUG-2857 | `unvalidated-foreign-key-reference` | `create_production_line`, `update_production_line` | A deleted machine can be attached to a line | Accepted | `Machine {id} not found`, nothing written; inactive machine accepted | P4 |
| BUG-2858 | `exclude-none-blocks-clear` | `update_production_line` (+ `ProductionLineUpdate`) | An edit cannot detach the machine or clear the description | `null` dropped, old value kept | `null` clears `machine_id` / `description`; `null` `name` / `is_active` → 422 (BUG-713 precedent) | P5 |
| BUG-2859 | `audit-stamp-on-noop` | `update_production_line` | `updated_by` stamped on an edit that changes nothing | Stamped on every call | HR-9 | HR-9 line |
| BUG-2860 | `audit-stamp-missing-on-change` | `delete_production_line` (+ service) | Switching a line off through delete records no one | `updated_by` untouched | `updated_by` = acting user when `is_active` changes; new `user_id` parameter | D2 |
| BUG-2861 | `lossy-error-mapping` | `app/services/production_line_service.py` (`create_production_line`) | Missing factory or machine on create answers 422, not 404 | Every `ValueError` → 422 | `… not found` → 404 `NotFoundError`, as on update; "does not belong to factory" stays 422 | D3 |

## Follow-ups for other reviews
| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **Production batch manager** (`production_batch_manager.py`, described in parallel) | Only `create_batch` refuses an inactive line; `start_batch`, `complete_batch` and `post_outputs_to_finished_goods` read the line raw. D2 relies on in-progress batches being able to finish; whether a **draft** batch on an inactive line may still be started is for that review. | D2 |
| FU-2 | **Machine manager** (`update_machine`) | O1's fix, once the owner answers. | O1 |
| FU-3 | **Production line service / endpoint** | BUG-2860 needs `user_id` passed to the delete; BUG-2855 needs `include_deleted` on `GET /production-lines/{id}/`; BUG-2861 mapping. | D2, P2, D3 |
| FU-4 | **Permissions (future, `docs/future/permissions.md`, not a question)** | Any active workspace member, whatever the role (viewer, ground-team included), can create, edit and switch off production lines; the list and get endpoints need only workspace membership. No role check exists on `/production-lines/`. | endpoint read |

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 54–56 | factory missing | `create` R2, R9 |
| 57–58 | factory in another workspace | `create` R3 |
| 54 (raw `get`) | factory soft-deleted / inactive not looked at | `create` R4 |
| 61 | `machine_id is not None` (0 included) / `None` | `create` R1, R5 |
| 62–64 | machine missing | `create` R5 |
| 65–66 | machine in another workspace | `create` R6 |
| 62 (raw `get`) | machine soft-deleted / inactive not looked at | `create` R7 |
| 68–71 | machine of another factory | `create` R8, R10 |
| 74–79 | dump, inject `workspace_id`, `created_by`; flush (FK on `created_by`) | `create` R1, R11, R12 |
| 111–113 | line missing | `update` R1, R9 |
| 116–117 | line in another workspace | `update` R2 |
| 111 (raw `get`) | line / factory state not looked at | `update` R3 |
| 120 | `machine_id is not None` (also equal to the current one) | `update` R5, R6 |
| 122–123 | machine missing | `update` R6 (a) |
| 124–125 | machine in another workspace | `update` R6 (b) |
| 121 (raw `get`) | machine soft-deleted not looked at | `update` R6 (c) |
| 127–130 | machine not in the line's factory | `update` R6 (d) |
| 133 | `exclude_unset`, `exclude_none` (nulls dropped; no `factory_id` in schema) | `update` R4, R5, R7 |
| 134 | `updated_by` always injected | `update` R8, R10 |
| 137 (`BaseDAO.update`) | sets each key, flushes | `update` R4 |
| 161–163 | id AND workspace; factory state not looked at | `get` R1–R3 |
| 188–191 | `factory_id is not None` → by factory (`active_only` ignored) | `list` R1, R2 |
| 192–195 | `active_only` → active of the workspace | `list` R3 |
| 196–199 | else → all of the workspace (no order, deleted factory not looked at) | `list` R4–R7 |
| 224–226 | line missing | `delete` R1 |
| 229–230 | line in another workspace | `delete` R2 |
| 233–235 | `is_active = False`, nothing else; no `updated_by`; already inactive → same write | `delete` R3–R6 |
