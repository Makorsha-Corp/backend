# Spec — `app/managers/production_formula_manager.py`

> **Status:** PAUSED. Production is deferred until the revamp (owner 2026-11-19); see docs/future/production-revamp.md.
> **Source commit:** e48a092

> **Review round 2026-11-19 (describe, under the reviewer's delegation of 2026-11-19).** Every item that is not money, stock quantities, order workflow or security was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. The house-rule lines stand. One owner question (stock) is parked as **OQ-F1** (number to be assigned when merged into `docs/testing/owner-questions.md`); its rules are written to today's behaviour and marked *pending OQ-F1*. Bug IDs BUG-2832 … BUG-2845 are **provisional** (block BUG-2832 … BUG-2851), not yet in `docs/testing/bugs.md`.

> **Below this manager.** `tests/unit/dao/production_formula.spec.md`, `production_formula_item.spec.md`, `production_formula_stage.spec.md`, `production_line.spec.md` and `base.spec.md` (all APPROVED) are not restated. Their FU-1 lists are the checklist for this manager; each item is answered below. Inherited `BaseDAO.create` builds the row from the dict and flushes; `update` sets every key of the dict that is an attribute and flushes; `remove` deletes by id and flushes, returning the deleted object.
>
> **Standing decisions applied here (not asked again):** an inactive formula is a normal, visible state and its code stays taken (formula DAO Q1, 2026-11-02); an inactive production line likewise (line DAO Q1); a recipe line of a removed catalog item stays visible (owner, 2026-11-02, item DAO Q1); deactivating a formula clears `is_default` (BUG-1329); HR-16 — another workspace's row is "not found". **Product cost rules fixed by the owner, cited not re-asked:** OQ-50 (production output has no cost, set by hand, revisit after launch), OQ-51 / BUG-2793 (`make_sellable`), BUG-2811 (a new product bucket records `avg_cost_before` NULL). This manager touches no cost and no stock; they matter only through the batch manager, which reads recipe output lines to post finished goods.
>
> **Verified by running** (my own script `v_formula_mgr.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddesc\formula\`, one transaction on `marker_test` with foreign-key triggers off (`SET LOCAL session_replication_role = replica`), rolled back, nothing committed): create with and without default; an empty update stamps `updated_by`; `null` leaves `description`, `unit`, `tolerance_percentage`, `machine_id` unchanged; an inactive formula created as default clears the active default; `is_default: true` on an inactive formula clears the active default; `is_active: false` keeps `is_default`; delete of an already inactive formula writes nothing; the other-workspace messages; duplicate code (also of an inactive formula; another workspace accepted); list with and without `active_only`; recipe lines of a removed item, a service item, the same item and role twice, all accepted; other-workspace / missing item, formula; invalid role through `model_construct`; empty role filter; stages on a line of a deleted factory, an inactive line, a removed item, a service item, all accepted; other-workspace item on a stage "not found"; rename of a stage whose machine was deleted refused, an empty update not; a stage row of another workspace on the same formula makes the insert fail with `IntegrityError` on `uq_formula_stage_order`; remove twice. **Read, not run:** `app/services/production_formula_service.py`, `app/api/v1/endpoints/production_formulas.py`, `app/core/exceptions.py` (status mapping), `ProductionBatchManager.create_batch`, `update_batch`, `_seed_stage_logs_from_formula`, `post_outputs_to_finished_goods`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs.

## Review
> Items are decided (delegation or house rule) except OQ-F1, which waits for the owner. The test designer can start: OQ-F1's rules are written to today's behaviour.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-9 | Saving a formula with nothing changed still records who changed it | bug (BUG-2832) | house rule |
| HR-6 | The full formula list has no display order | bug (BUG-2838) | house rule |
| HR-1 | A stage name of only spaces is accepted; names kept with their spaces | bug (BUG-2845) | house rule |
| P1 | A formula's description and estimated time cannot be emptied | bug (BUG-2833) | Claude, delegated (BUG-942 precedent) |
| P2 | A recipe line's unit and tolerance cannot be emptied | bug (BUG-2834) | Claude, delegated (BUG-942 precedent) |
| P3 | A stage's line, machine, expected values and notes cannot be emptied | bug (BUG-2835) | Claude, delegated (BUG-942 precedent) |
| P4 | Clearing the default flag on other formulas does not record who did it | bug (BUG-2836) | Claude, delegated (BUG-881 precedent) |
| P5 | An inactive formula can be made the default | bug — refused (BUG-2837) | Claude, delegated (BUG-1329 precedent) |
| P6 | A removed catalog item can be put on a recipe | bug — "not found" (BUG-2839) | Claude, delegated (BUG-2780 precedent) |
| P7 | A stage accepts a removed item, or a line of a deleted factory | bug — "not found" (BUG-2840) | Claude, delegated (BUG-2341 / BUG-1312 precedent) |
| P8 | Editing a stage re-checks references the edit does not touch; a stage whose machine was deleted cannot be renamed | bug (BUG-2841) | Claude, delegated (BUG-2341 precedent) |
| P9 | The same item can be on one recipe twice in the same role | bug — refused (BUG-2842) | Claude, delegated (BUG-2338 precedent) |
| P10 | A stage number taken at the database level gives a generic "already exists" error | bug (BUG-2843) | Claude, delegated (BUG-2781 precedent) |
| D1 | "Invalid item_role" lists the roles in a different order each run | bug (BUG-2844) | Claude, delegated |
| D2 | Removing a recipe line or stage deletes it outright, with no trace | intended | Claude, delegated |
| D3 | A formula can be deactivated while batches using it are open | intended | Claude, delegated |
| D4 | A stage's machine need not be on the stage's line | intended | Claude, delegated |
| D5 | The manager repeats the role check the request schema already makes | intended | Claude, delegated |
| D6 | Swapping two stage numbers needs a spare number in between | intended | Claude, delegated |
| OQ-F1 | A service (non-stock item) can be a recipe input or output | **pending — owner** (stock) | owner |

Already logged, no new ID: BUG-1316 (code uniqueness, HR-2), BUG-1317 (blank code / name, HR-1), BUG-1318 (`limit` ≤ 0, HR-7), BUG-1314 / BUG-1315 / BUG-1319 / BUG-1320 / BUG-100 (DAO orders, HR-6), BUG-1022 (other-workspace message, HR-16), BUG-1329 (deactivation keeps default).

### House-rule violations — applied automatically

- **HR-9** `update_formula` R8 — `updated_by` is written on every call, even an empty body or values equal to the stored ones (verified: empty body, `updated_by` `None` → 2), and `updated_at` moves with it. Intended: `updated_by` written only when at least one field actually changes value; otherwise the row is returned untouched.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-2832 (pattern `audit-stamp-on-noop`). Rules: `update_formula` R8.
- **HR-6** `get_formulas` R3 — without `active_only` the list comes from `get_by_workspace`, which after BUG-100 is ordered by `id` only; that is a stable page, not a display order (formula DAO FU-1 (a)). Intended: `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit` — the same order BUG-1314 gives the `active_only` list.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2838 (pattern `hr-6-non-default-list-order`). Rules: `get_formulas` R3.
- **HR-1** `add_formula_stage` R7, `update_formula_stage` R9 — `ProductionFormulaStageCreate` / `ProductionFormulaStageUpdate` give `name` `min_length=1` only: `"   "` passes and `" Spin "` is stored with its spaces (read; BUG-1317 is the same for formula code and name). Intended: stored trimmed; blank or whitespace-only rejected by the schema (422), nothing written.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2845 (pattern `blank-name-accepted`). Fix in `app/schemas/production_formula_stage.py`. Rules: `add_formula_stage` R7, `update_formula_stage` R9.

Checked and **not** a new line here: **HR-2** — formula code: BUG-1316 (existing) covers trimming, case, the index and the lost race (formula DAO FU-1 (b)); stage names and recipe lines are not meant to be unique by name. **HR-1** — formula code / name: BUG-1317 (existing). **HR-3** — `unit` on a recipe line is informational, neither grouped nor filtered (item DAO). **HR-4** — none of the three tables has a soft-delete column; an inactive formula is a state (Q1 of the formula DAO). **HR-5** — every filter is in the query. **HR-7** — BUG-1318 (existing) for `GET /production-formulas/`; nothing else pages. **HR-8** — no `LIKE`. **HR-10** — nothing here moves money or stock or decides an approval; the worst a race does is two defaults (the flag is read by nothing, formula DAO Q2) or the stage-order constraint error (P10). **HR-11 … HR-14** — no externals, no batch jobs. **HR-15** — no money; `tolerance_percentage` is a percentage in `Numeric(5,2)` and the schema keeps it in 0–100. **HR-16** — the formula, line, machine, recipe line and stage are all looked up in the caller's workspace; the item in `add_formula_item` and the formula in `update_formula` / `delete_formula` give a different message for another workspace's row: BUG-1022 (existing). A recipe line or stage row of another workspace on this formula (invalid data) is ignored by every read and by the stage-order check (it is caught only by the constraint: P10).

**Permission checks:** none — any member of the workspace can create, edit and deactivate formulas, recipe lines and stages (note for `docs/future/permissions.md`, reported to the caller).

### Owner question — pending

### OQ-F1. OWNER, stock — A service can be a recipe input or output
**Background:** Catalog items have a type: `physical` (stock is kept) or `service` (no stock; e.g. "Dyeing fee"). A recipe (formula) lists the items a batch uses (`input`) and makes (`output`, `byproduct`, `waste`). When a completed batch has no output lines of its own and its recipe has **exactly one** output line, "post finished goods" books the batch's whole output quantity as finished goods of that item (`ProductionBatchManager.post_outputs_to_finished_goods`). Nothing in that path looks at the item type.
**What happens today:** Any item of the workspace can be put on a recipe in any role, a service included (verified: a service accepted as `output`).
**Example:** Recipe "Dyed yarn" is set up with one output line, the service "Dyeing fee". Batch B-31 completes with output 500 and no output lines: 500 units of "Dyeing fee" appear in finished goods, for sale like any product.
**Rules affected:** `add_formula_item` R6, `update_formula_item` (no rule: the item cannot be changed on a line); `_validate_stage_refs` R6a (a stage's expected output follows the answer — decided by Claude under the delegation, 2026-11-19).
**Recommended answer:** **(a)** — a recipe line must be a physical item, in every role; a service is refused with 400 `"{item name}" is a service and cannot be on a recipe`, nothing written. Existing lines stay as they are and stay visible (as the owner ruled for removed items, 2026-11-02). Labour and fees can be added to recipes when production costing is built (OQ-50, revisit after launch).
**Options, in plain words:**
- **(a) Refuse services on every recipe line (recommended).** A recipe is a list of things you physically use and make. Services never sit in a stock room, so the system will not let anyone put one on a recipe at all. This removes the risk that a batch creates stock of something that cannot exist. The cost of labour or outside work cannot be recorded on the recipe yet, but recipes carry no cost today anyway (your OQ-50 decision), so nothing is lost now.
- **(b) Allow services only as inputs.** A recipe may list a service it uses, such as "Dyeing fee", so the recipe page shows the full picture of what a batch needs; services may not be outputs, byproducts or waste, so a batch can never turn into stock of a service. The input line is information only: nothing deducts or charges it today.
- **(c) Keep today's behaviour.** Any item can be on a recipe in any role. The people setting up recipes must take care never to make a service an output, or completed batches can put service "stock" into finished goods, which then shows up as sellable.
**Answer:** _pending_

### Decided under the reviewer's delegation (2026-11-19)

### P1. A formula's description and estimated time cannot be emptied — 🐞 BUG-2833
**Background:** `update_formula` drops every field sent as `null` (`exclude_none`). The owner ruled the same a bug for items (BUG-942) and products (BUG-2777).
**What happens today:** `{"description": null}` → 200, the old text kept (verified).
**Example:** A user empties the description "Old blend — do not use" and saves; it is still shown.
**Rules affected:** `update_formula` R9
**Answer:** bug — per BUG-942 precedent: an explicit `null` clears `description` and `estimated_duration_minutes`; `null` for `name`, `is_active`, `is_default` → 422 (schema); omitted fields unchanged (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2833 (pattern `exclude-none-blocks-clear`). Fix in `update_formula` and `app/schemas/production_formula.py`.

### P2. A recipe line's unit and tolerance cannot be emptied — 🐞 BUG-2834
**Background:** As P1, for `update_formula_item` (item DAO FU-1 (d)).
**What happens today:** `{"unit": null, "tolerance_percentage": null}` → both kept (verified: `kg`, `5`).
**Example:** A ±5 % tolerance was set by mistake on "Raw cotton"; the user empties it and saves; the recipe still says ±5 %.
**Rules affected:** `update_formula_item` R5
**Answer:** bug — per BUG-942 precedent: explicit `null` clears `unit` and `tolerance_percentage`; `null` for `item_role`, `quantity`, `is_optional` → 422 (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2834 (pattern `exclude-none-blocks-clear`). Fix in `update_formula_item` and `app/schemas/production_formula_item.py`.

### P3. A stage's line, machine, expected values and notes cannot be emptied — 🐞 BUG-2835
**Background:** As P1, for `update_formula_stage`. A stage cannot be detached from its line or machine.
**What happens today:** `{"machine_id": null, "notes": null}` → both kept (verified).
**Example:** The spinning stage was tied to machine "M1", which is being scrapped. The user clears the machine and saves; the stage still names M1, and once M1 is deleted the stage cannot be edited at all (P8).
**Rules affected:** `update_formula_stage` R6
**Answer:** bug — per BUG-942 precedent: explicit `null` clears `production_line_id`, `machine_id`, `expected_duration_minutes`, `expected_output_quantity`, `expected_output_item_id`, `notes`; `null` for `name`, `stage_order` → 422; a cleared reference is not checked (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2835 (pattern `exclude-none-blocks-clear`). Fix in `update_formula_stage` and `app/schemas/production_formula_stage.py`.

### P4. Clearing the default flag on other formulas does not record who did it — 🐞 BUG-2836
**Background:** Making formula B the default switches the flag off on the old default A. A's `updated_at` moves (column `onupdate`), but its `updated_by` keeps the previous editor (formula DAO FU-1 (f)). BUG-881 ruled that a change to a row must record who made it.
**What happens today:** A shows "last changed by" someone who never touched the flag (verified: `updated_by` stayed `None`).
**Example:** Rahim makes "Yarn v2" the default on Monday. "Yarn v1" now shows "last changed Monday by Karim", who last edited it a month ago.
**Rules affected:** `_clear_other_defaults` R5
**Answer:** bug — per BUG-881 precedent: each formula whose flag is switched off gets `updated_by` = the acting user (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2836 (pattern `audit-stamp-missing-on-change`). *(requires new parameter `user_id` on `_clear_other_defaults`)*

### P5. An inactive formula can be made the default — 🐞 BUG-2837
**Background:** BUG-1329 decided that an inactive formula never holds the default flag (deactivating clears it). Two other paths still give one the flag: creating a formula with `is_active: false, is_default: true`, and `is_default: true` on a formula that is inactive. Both also switch the flag off on the active default, so the workspace is left with no active default.
**What happens today:** both accepted (verified): the inactive formula is the default, and the active one lost the flag.
**Example:** "Yarn v1" is the default. A user ticks "default" on the retired "Yarn v0": v1 loses the flag, and v0 — which batches cannot use — is the default.
**Rules affected:** `create_formula` R4, `update_formula` R7
**Answer:** bug — per BUG-1329 precedent: refused with `ValueError("An inactive formula cannot be the default formula")` (422 at the API), nothing written, no other formula changed; `is_active: true` and `is_default: true` in one request on an inactive formula is accepted (it ends up active) (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2837 (pattern `flag-survives-deactivation`).

### P6. A removed catalog item can be put on a recipe — 🐞 BUG-2839
**Background:** A catalog item is removed by `is_active = False`. The owner ruled (2026-11-02) that an **existing** recipe line of a removed item stays visible; what a **new** line should do was left to this manager (item DAO FU-1 (a)). BUG-2780 ruled that a product cannot be created for a removed item.
**What happens today:** `add_formula_item` accepts a removed item (verified).
**Example:** "Old dye" was removed from the catalog last month. A user still picks it for the new recipe "Blue yarn"; batches then list a material nobody can buy or stock.
**Rules affected:** `add_formula_item` R5
**Answer:** bug — per BUG-2780 precedent: a removed item is treated as not found, `ValueError("Item {item_id} not found")` (404 at the API), nothing written; existing lines are untouched (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2839 (pattern `reference-to-soft-deleted-row-accepted`).

### P7. A stage accepts a removed item, or a line of a deleted factory — 🐞 BUG-2840
**Background:** A stage may name a production line, a machine and an expected output item. The machine check refuses a deleted machine; the line and item checks look only at the workspace. Lines of a deleted factory are hidden from the line lists (BUG-1312); BUG-2341 refused deleted references on templates.
**What happens today:** a line whose factory is soft-deleted, and a removed item, are both accepted (verified). An inactive line is accepted, which is intended (line DAO Q1).
**Example:** Factory "Old Plant" was deleted. A new stage "Wash" is set to its "Line 2"; batches made from the recipe seed a stage log on a line no list shows.
**Rules affected:** `_validate_stage_refs` R3, R6
**Answer:** bug — per BUG-2341 / BUG-1312 precedent: a line whose factory is soft-deleted → `Production line {id} not found`; a removed item → `Item {id} not found`; nothing written; an inactive line or an inactive-but-live factory is accepted (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2840 (pattern `reference-to-soft-deleted-row-accepted`).

### P8. Editing a stage re-checks references the edit does not touch — 🐞 BUG-2841
**Background:** `update_formula_stage` checks the line, machine and item using the sent value or, when not sent, the stored one. A stored machine that has since been deleted therefore fails every edit. BUG-2341 decided that an update leaving a stored value unchanged is accepted.
**What happens today:** renaming a stage whose machine was deleted → `Machine {id} not found` (verified); and the machine cannot be cleared (P3).
**Example:** Machine "M1" is deleted. The user renames stage "Spin" to "Ring spin": refused with "Machine 17 not found", although they only changed the name.
**Rules affected:** `update_formula_stage` R3
**Answer:** bug — per BUG-2341 precedent: only references sent in the request (and not `null`) are checked; stored ones are not re-checked (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2841 (pattern `unchanged-reference-revalidated`).

### P9. The same item can be on one recipe twice in the same role — 🐞 BUG-2842
**Background:** Nothing stops a second line with the same item and role (item DAO FU-1 (c)). "Post finished goods" counts output lines: two output lines of one item count as two outputs, so it refuses to post. BUG-2338 refused the same item twice on a work order template.
**What happens today:** a second `output` line of "Yarn" is accepted (verified).
**Example:** "Yarn" is added as output twice by a double click. A completed batch with no output lines of its own can no longer be posted: "No quantities to post".
**Rules affected:** `add_formula_item` R8, `update_formula_item` R6
**Answer:** bug — per BUG-2338 precedent: an item already on the formula in the same role is refused with `ValueError('"{item name}" is already a {role} line of this formula')` (422 at the API), nothing written; the same item in another role is allowed (e.g. input and byproduct); a unique index on `(formula_id, item_id, item_role)` backs it up and a lost race gets the same refusal (check real data first: `SELECT formula_id, item_id, item_role, count(*) FROM production_formula_items GROUP BY 1, 2, 3 HAVING count(*) > 1`) (decided by Claude under the reviewer's delegation, 2026-11-19; not a stock rule: today's outcome of a duplicate is already a refusal to post)
**Resolution:** 🐞 BUG-2842 (pattern `duplicate-child-row-accepted`).

### P10. A stage number taken at the database level gives a generic error — 🐞 BUG-2843
**Background:** Stage numbers are unique per formula by a database constraint (`uq_formula_stage_order`). The manager checks first, but only among stages of the caller's workspace, and two requests at once both pass the check (stage DAO FU-1 (b)). BUG-2781 ruled that a unique conflict must give the specific message.
**What happens today:** the insert fails with `IntegrityError` (verified with a stage row of another workspace on the same formula), and the API answers its generic 409 "This resource already exists. Please use a different value."
**Example:** Two planners add stage 3 to "Blue yarn" at once; one gets a message that names nothing.
**Rules affected:** `add_formula_stage` R4, `update_formula_stage` R5
**Answer:** bug — per BUG-2781 precedent: the constraint violation surfaces as the normal refusal `Stage order {n} already exists for this formula` (422), the rest of the session usable (savepoint) (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2843 (pattern `unique-conflict-not-checked`).

### D1. "Invalid item_role" lists the roles in a different order each run — 🐞 BUG-2844
**Background:** The valid roles are a Python `set`; the message joins it. String hashing is randomised per process, so the order changes between server restarts. Reachable only by internal callers: the API refuses a bad role in the schema or query pattern first (D5).
**What happens today:** `Invalid item_role 'Input'. Must be one of: waste, input, byproduct, output` (verified, one run).
**Example:** A test asserting the message passes on one run and fails on the next.
**Rules affected:** `add_formula_item` R7, `update_formula_item` R4, `get_formula_items` R5
**Answer:** bug — the roles are listed in the fixed order `input, output, waste, byproduct` (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2844 (pattern `unstable-message-order`).

### D2. Removing a recipe line or stage deletes it outright — ✅ intended
**Background:** Recipe lines and stages have no audit or soft-delete columns. A batch's stage log keeps its stage name when its stage is removed (`formula_stage_id` → NULL, stage-log DAO R5); batch lines are not copied from recipe lines.
**What happens today:** the row is deleted; nothing records it.
**Example:** A user removes "Dye 50 L" from a recipe; no history shows it was there.
**Rules affected:** `remove_formula_item` R2, `remove_formula_stage` R2
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-19: a recipe line is a definition, not a stock or money record; the hard-delete-leaves-no-trace bugs were for orders). Who changed a recipe is a note for `docs/future/permissions.md`.

### D3. A formula can be deactivated while batches using it are open — ✅ intended
**Background:** "Delete" sets the formula inactive (formula DAO Q1: a switch). `create_batch` refuses an inactive formula; batches already made keep their link and stage logs.
**What happens today:** deactivation never looks at batches.
**Example:** "Yarn v1" is deactivated while batch B-40 runs on it; B-40 carries on, no new batch can pick v1.
**Rules affected:** `delete_formula` R5
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-19: deactivating only stops new use; nothing is lost and it can be switched back on).

### D4. A stage's machine need not be on the stage's line — ✅ intended
**Background:** Each reference is checked on its own; a batch's stage log copies only the stage's line.
**What happens today:** line "L1" in Factory A with machine "M9" in Factory B is accepted.
**Example:** The route shows "Spin — L1 — M9"; nothing else follows from it.
**Rules affected:** `_validate_stage_refs` R7
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-19: the stage's machine and line are planning hints; no stock or posting reads the machine).

### D5. The manager repeats the role check the schema already makes — ✅ intended
**Background:** `item_role` is limited to `input|output|waste|byproduct` by the request schemas and by the `item_role` query pattern of `GET /production-formulas/{id}/items/`; the manager checks again (item DAO FU-1 (e)).
**What happens today:** the manager's branches are reachable only by internal callers (verified with `model_construct`).
**Rules affected:** `add_formula_item` R7, `update_formula_item` R4, `get_formula_items` R5
**Answer:** intended — keep as defence for internal callers; not dead code (decided by Claude under the reviewer's delegation, 2026-11-19).

### D6. Swapping two stage numbers needs a spare number — ✅ intended
**Background:** There is no reorder action; each edit is checked against the other stages.
**What happens today:** to swap stages 1 and 2, the user moves 1 → 99, 2 → 1, 99 → 2.
**Rules affected:** `update_formula_stage` R4
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-19: a reorder action is a feature, not a fix).

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here.

| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **Production batch manager** (`post_outputs_to_finished_goods`, `complete_batch`) | (a) The single-output fallback reads the formula's **current** output lines when posting, not those at batch start: a recipe edited while a batch runs changes which item gets the stock. Stock rule — if raised, ask the owner once there (suggested: batches post to the recipe's output as it was when the batch started, or recipe output lines cannot change while a batch on that recipe is open). (b) `update_batch` accepts an inactive formula; `create_batch` refuses one. (c) `ProductionBatchService.start_batch` docstring says it "creates batch items" from the formula; the manager does not. (d) OQ-F1's answer may also need a check at posting time for existing service lines. | reading the callers |
| FU-2 | **Production formula service** | Error mapping, for its spec: `create_formula` maps every `ValueError` to 422; `update_formula`, `add_formula_item`, `update_formula_item`, `add_formula_stage`, `update_formula_stage`, `get_formula_items` map a message containing `not found` to 404, else 422; `delete_formula`, `remove_formula_item`, `remove_formula_stage`, `get_formula_stages` map every `ValueError` to 404. New messages (BUG-2837, BUG-2842, BUG-2843) must not contain `not found`. TC1–TC6 (`tests/unit/services/base_service.spec.md`) apply to the write methods. | Overview |
| FU-3 | **Permissions** (`docs/future/permissions.md`) | Any workspace member can create, edit, deactivate formulas and add / change / remove recipe lines and stages; recipe lines and stages record no author or time. The stage endpoints do not even take the current user. | all writes |

## Overview
`ProductionFormulaManager` keeps the workspace's production recipes: a formula (code, name, version, estimated time, active and default flags), its recipe lines (`production_formula_items`: item, role `input` / `output` / `waste` / `byproduct`, whole-number quantity, unit, optional flag, tolerance) and its route (`production_formula_stages`: numbered stages with an optional line, machine and expected output). It is the CRUD behind `/production-formulas/` through `ProductionFormulaService`, which commits. It protects: one code per workspace (Python check), at most one default (by clearing others), stage numbers unique per formula, and workspace isolation of every reference. It moves no stock and no money; `ProductionBatchManager` reads the formulas, lines and stages it keeps (batch check, stage seeding, single-output posting fallback). It never commits and takes no lock.

**Callables:** 15 specified · 3 not specified
**Externals to mock:** `utcnow` (`app.utils.time`, through `created_at` / `updated_at` defaults of `production_formulas`) only if a case asserts their value.
**Integration-only behavior:** none.

**Errors are `ValueError`** with the message given; the API status comes from the service (FU-2): 404 for messages containing `not found` (and always for delete / remove / list stages), else 422 (`BusinessRuleError`). Schema failures are `pydantic.ValidationError` (422).

**Inputs (schemas):**
- `ProductionFormulaCreate`: `formula_code` str 1–50 (required), `name` str 1–200 (required), `description` str|None, `version` int ≥ 1 (default 1), `estimated_duration_minutes` int ≥ 0 | None, `is_active` (default `True`), `is_default` (default `False`).
- `ProductionFormulaUpdate`: `name` 1–200, `description`, `estimated_duration_minutes` ≥ 0, `is_active`, `is_default` — all optional, default `None`. `formula_code` and `version` cannot be changed.
- `ProductionFormulaItemCreate`: `formula_id`, `item_id` int (required), `item_role` pattern `^(input|output|waste|byproduct)$`, `quantity` int > 0, `unit` ≤ 20 | None, `is_optional` (default `False`), `tolerance_percentage` Decimal 0–100 | None. `ProductionFormulaItemUpdate`: `item_role`, `quantity`, `unit`, `is_optional`, `tolerance_percentage`, all optional; `formula_id` / `item_id` cannot be changed.
- `ProductionFormulaStageCreate`: `formula_id` int, `name` 1–200, `stage_order` int ≥ 1, `production_line_id`, `machine_id`, `expected_output_item_id` int|None, `expected_duration_minutes`, `expected_output_quantity` int ≥ 0 | None, `notes`. `ProductionFormulaStageUpdate`: the same without `formula_id`, all optional.
- Unknown extra fields are ignored (Pydantic default).

**Model facts:** `production_formulas` — see the formula DAO spec (no unique constraint; `version`, `is_active`, `is_default` Python defaults; `created_by`, `updated_by` FK profiles SET NULL; `updated_at` `onupdate`). `production_formula_items` — `workspace_id`, `formula_id` (FK CASCADE), `item_id` (FK RESTRICT), `item_role` String(20), `quantity` Integer NOT NULL, `unit`, `is_optional` default `False`, `tolerance_percentage` Numeric(5,2); no audit columns, no unique constraint. `production_formula_stages` — `formula_id` FK CASCADE, `stage_order` NOT NULL, `name` String(200), `production_line_id` / `machine_id` / `expected_output_item_id` FK SET NULL, unique `uq_formula_stage_order (formula_id, stage_order)`; no audit columns. `production_batch_stage_logs.formula_stage_id` → stages ON DELETE SET NULL.

**Notes for the test designer:**
- `from app.managers.production_formula_manager import production_formula_manager`. Arguments are positional or keyword as named in the headers (`session` first).
- Parents: `make_workspace` from `tests/unit/factories.py`; `Item(workspace_id, name, name_normalized, unit)` (`is_active=False` = removed; `item_type="service"` = service); `Factory(workspace_id, name, abbreviation)` (`is_deleted=True` = deleted); `ProductionLine(workspace_id, factory_id, name)`; `Machine(workspace_id, name, factory_id)`. `user_id` must be a `profiles` row (FK) unless the test turns FK triggers off.
- The roles message order is random today (D1): until BUG-2844 is fixed, assert the message with a set comparison of the listed roles, or use the strict-xfail card for the fixed order.
- P10 / BUG-2843 without two transactions: insert a stage row with **another** workspace's `workspace_id` on the same formula and the same `stage_order` (invalid data, hidden from the check), then call `add_formula_stage` inside `with session.begin_nested():`. Today `IntegrityError` (`.orig.pgcode == "23505"`), strict xfail.
- Concurrency (two defaults at once) needs two transactions; no unit case.

## Not specified
- `ProductionFormulaManager.__init__` — wires the formula, recipe-line and stage DAOs; no logic.
- `ProductionFormulaManager.VALID_ITEM_ROLES` — constant `{'input', 'output', 'waste', 'byproduct'}`, used by the role checks.
- `production_formula_manager` — module singleton. Inherited `BaseManager` methods — `tests/unit/managers/base_manager.spec.md`; no caller uses them on this manager. (`get_formula_base_output` was removed as dead code; not in the source.)

---

## `ProductionFormulaManager.create_formula(session, formula_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.create_formula` ← `POST /production-formulas/`)

**Purpose:** Add a recipe to the workspace, optionally as its default.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `formula_data` | `ProductionFormulaCreate` | as Overview |
| `workspace_id` | int | the new row's workspace; scope of the code check and of the default clearing |
| `user_id` | int | stored as `created_by` |

**Returns:** the new `ProductionFormula`, flushed, not committed.

**Rules:**
- **R1.** A `formula_code` already used by a formula of this workspace — active or inactive (✅ formula DAO Q1) — is refused: `Formula code '{code}' already exists in this workspace`, nothing written (verified for both). Detection follows `get_by_formula_code`; [BUG-1316] (HR-2) after the fix it is trimmed, case-insensitive, backed by a unique index, and a lost race gets the same refusal. *(Today: exact match, Python only.)*
- **R2.** The same code in another workspace does not conflict (verified).
- **R3.** With `is_default: true` (and the formula active), every other active default of this workspace loses the flag (`_clear_other_defaults` R1–R6), then the new row is stored with `is_default = True`. With `is_default: false` no other formula changes.
- **R4.** [BUG-2837] `is_active: false` with `is_default: true` → `ValueError("An inactive formula cannot be the default formula")`, nothing written, no other formula changed. *(Today: stored as an inactive default, and the active default loses its flag, verified.)*
- **R5.** The row has every schema field as sent (defaults: `version` 1, `is_active` `True`, `is_default` `False`, `description` / `estimated_duration_minutes` `NULL`), `workspace_id` = the argument, `created_by` = `user_id`, `updated_by` `NULL`, `created_at` = `updated_at` = now.
- **R6.** [BUG-1317] (HR-1, schema) `formula_code` and `name` are stored trimmed; blank or whitespace-only → 422, nothing written. *(Today: `"   "` accepted, spaces kept.)*
- **R7.** Check order: schema, then R1, then R4, then the clearing (R3), then the insert.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| code taken in this workspace | `ValueError` (422) | `Formula code '{formula_code}' already exists in this workspace` |
| inactive and default (BUG-2837) | `ValueError` (422) | `An inactive formula cannot be the default formula` |
| schema | `pydantic.ValidationError` (422) | — |

**Side effects:** one `production_formulas` row; possibly `is_default = False` on other formulas of the workspace; flushed.

---

## `ProductionFormulaManager.update_formula(session, formula_id, formula_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.update_formula` ← `PUT /production-formulas/{id}/`)

**Purpose:** Change a recipe's name, description, estimated time, active or default flag.

**Inputs:** `formula_id` int; `formula_data` `ProductionFormulaUpdate`; `workspace_id`; `user_id` (stored as `updated_by`).

**Returns:** the updated `ProductionFormula`, flushed, not committed.

**Rules:**
- **R1.** An unknown id → `Production formula {formula_id} not found`.
- **R2.** [BUG-1022] (HR-16) A formula of another workspace gets exactly R1's answer and status. *(Today: `Production formula {id} does not belong to workspace {workspace_id}` (verified), 422 at the API.)* Nothing written.
- **R3.** Only fields sent (and not `null`, see R9) change; `formula_code`, `version`, `workspace_id`, `created_by` cannot be changed.
- **R4.** `is_default: true` → every other active default of this workspace loses the flag (`_clear_other_defaults`, this formula excluded), and this one gets it. Already the default → stays, others unaffected.
- **R5.** `is_default: false` → this formula loses the flag; no other formula becomes default (a workspace may have none).
- **R6.** [BUG-1329] `is_active: false` also sets `is_default = False`; `is_active: true` later does not restore it. *(Today: the flag is kept, verified.)*
- **R7.** [BUG-2837] `is_default: true` on a formula that is inactive and stays inactive (no `is_active: true` in the same request), or together with `is_active: false` → `ValueError("An inactive formula cannot be the default formula")`, nothing written, no other formula changed. *(Today: accepted, and the active default loses its flag, verified.)*
- **R8.** [BUG-2832] (HR-9) `updated_by` = `user_id` only when at least one field changes value; an empty body or equal values return the row untouched (no `updated_by`, no `updated_at` move). *(Today: always stamped, verified.)*
- **R9.** [BUG-2833] An explicit `null` clears `description` and `estimated_duration_minutes`; `null` for `name`, `is_active`, `is_default` → 422 (schema). *(Today: every `null` is dropped, verified.)*
- **R10.** [BUG-1317] (HR-1) `name` stored trimmed; blank → 422.
- **R11.** ✅ An inactive formula can be edited like an active one (formula DAO Q1).
- **R12.** Check order: R1/R2, then R7, then the clearing (R4), then the write.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown id (and, after BUG-1022, another workspace) | `ValueError` (404) | `Production formula {formula_id} not found` |
| another workspace (today) | `ValueError` (422) | `Production formula {formula_id} does not belong to workspace {workspace_id}` |
| inactive default (BUG-2837) | `ValueError` (422) | `An inactive formula cannot be the default formula` |

**Side effects:** this row's sent fields, `updated_by`, `updated_at`; possibly `is_default` on other formulas; flushed.

---

## `ProductionFormulaManager.get_formula(session, formula_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaService.get_formula` ← `GET /production-formulas/{id}/`, which turns `None` into 404 `Production formula with ID {id} not found`)

**Purpose:** One recipe of this workspace.

**Returns:** the `ProductionFormula` or `None`.

**Rules:**
- **R1.** A formula of this workspace is returned, active or inactive (✅ formula DAO Q1; verified).
- **R2.** An unknown id or a formula of another workspace → `None` (verified).
- **R3.** Nothing is written.

**Errors:** none. **Side effects:** none.

---

## `ProductionFormulaManager.get_formulas(session, workspace_id, active_only=False, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaService.get_formulas` ← `GET /production-formulas/?active_only=&skip=&limit=`; the endpoint caps `limit` at 100)

**Purpose:** The workspace's recipes, one page.

**Returns:** `list[ProductionFormula]`, possibly empty.

**Rules:**
- **R1.** `active_only` false (default) → every formula of this workspace, active and inactive (verified); `active_only` true → only active ones (verified). Other workspaces never appear.
- **R2.** At most `limit` rows after skipping `skip`, the filter applied before paging (DAO R4–R6: `limit 0` → `[]`, negative values → `DataError`). [BUG-1318] (HR-7) the endpoint refuses `limit < 1` with 422.
- **R3.** [BUG-2838] (HR-6) without `active_only` the rows are ordered `name` case-insensitive ascending, then `id` ascending, before paging. *(Today: `id` order after BUG-100; database order before it.)* With `active_only` the same order comes from [BUG-1314].

**Errors:** none (DAO `DataError` on negative paging). **Side effects:** none.

---

## `ProductionFormulaManager.delete_formula(session, formula_id, workspace_id, user_id)`
**Shape:** soft-delete (deactivate)
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.delete_formula` ← `DELETE /production-formulas/{id}/`, 204)

**Purpose:** Switch a recipe off so new batches cannot use it.

**Returns:** the `ProductionFormula`.

**Rules:**
- **R1.** Unknown id → `Production formula {formula_id} not found`.
- **R2.** [BUG-1022] (HR-16) another workspace → R1's answer. *(Today: `… does not belong to workspace {workspace_id}`, verified; 404 at the API either way.)*
- **R3.** An active formula → `is_active = False`, `is_default = False`, `updated_by = user_id`; flushed.
- **R4.** An already inactive formula is returned unchanged; nothing written, `updated_by` not stamped (verified). A legacy inactive row still holding `is_default = True` keeps it (BUG-1329 stops new ones).
- **R5.** ✅ (D3) Recipe lines, stages and batches are not touched; open batches do not block; the formula's code stays taken (formula DAO Q1).

**Errors:** as R1 / R2. **Side effects:** as R3.

---

## `ProductionFormulaManager.add_formula_item(session, item_data, workspace_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.add_formula_item` ← `POST /production-formulas/{formula_id}/items/`; the endpoint first refuses a body `formula_id` different from the path with 422 `Path formula_id ({path}) does not match body formula_id ({body})`)

**Purpose:** Add a recipe line.

**Inputs:** `item_data` `ProductionFormulaItemCreate` (Overview); `workspace_id`.

**Returns:** the new `ProductionFormulaItem`, flushed.

**Rules:**
- **R1.** The formula must be a formula of this workspace, else `Production formula {formula_id} not found` (unknown or another workspace, verified). An inactive formula is accepted (✅ formula DAO Q1; verified).
- **R2.** Unknown `item_id` → `Item {item_id} not found` (verified).
- **R3.** [BUG-1022] (HR-16) an item of another workspace gets R2's answer and status. *(Today: `Item {item_id} does not belong to workspace {workspace_id}`, verified, 422.)*
- **R4.** Quantity, unit, optional flag and tolerance are checked only by the schema (`quantity` whole number > 0, `unit` ≤ 20 characters, `tolerance_percentage` 0–100); the manager adds no check of its own. `tolerance_percentage` is stored to 2 decimals by the column (`Numeric(5,2)`).
- **R5.** [BUG-2839] A removed item (`is_active = False`) → `Item {item_id} not found`, nothing written. *(Today: accepted, verified.)*
- **R6.** *Pending OQ-F1.* Today a service item (`item_type = 'service'`) is accepted in any role (verified).
- **R7.** A role outside `input, output, waste, byproduct` (reachable only past the schema, ✅ D5) → `Invalid item_role '{role}'. Must be one of: input, output, waste, byproduct` [BUG-2844] — fixed order. *(Today: the roles in random order.)*
- **R8.** [BUG-2842] The item already on this formula in the same role → `"{item name}" is already a {role} line of this formula`, nothing written; the same item in another role is allowed. *(Today: accepted, verified.)*
- **R9.** The row has the sent fields, `workspace_id` = the argument, `is_optional` default `False`.
- **R10.** Check order: R1, R2, R3, R5, (OQ-F1), R7, R8, then the insert.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| formula not in workspace | `ValueError` (404) | `Production formula {formula_id} not found` |
| item unknown / removed (BUG-2839) / other workspace (BUG-1022) | `ValueError` (404) | `Item {item_id} not found` |
| item of another workspace (today) | `ValueError` (422) | `Item {item_id} does not belong to workspace {workspace_id}` |
| bad role (internal only) | `ValueError` (422) | `Invalid item_role '{role}'. Must be one of: input, output, waste, byproduct` |
| duplicate (BUG-2842) | `ValueError` (422) | `"{item name}" is already a {role} line of this formula` |

**Side effects:** one `production_formula_items` row, flushed.

---

## `ProductionFormulaManager.update_formula_item(session, formula_item_id, item_data, workspace_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.update_formula_item` ← `PUT /production-formulas/items/{id}/`)

**Purpose:** Change a recipe line's role, quantity, unit, optional flag or tolerance.

**Returns:** the `ProductionFormulaItem`, flushed.

**Rules:**
- **R1.** A line not of this workspace (unknown or another workspace) → `Formula item {formula_item_id} not found` (verified).
- **R2.** Sent fields change; `formula_id`, `item_id` cannot. The formula's state is not checked (inactive accepted).
- **R3.** An empty body returns the line unchanged (verified).
- **R4.** A sent role outside the four (internal only, ✅ D5) → R7 of `add_formula_item`'s message [BUG-2844].
- **R5.** [BUG-2834] explicit `null` clears `unit` and `tolerance_percentage`; `null` for `item_role`, `quantity`, `is_optional` → 422. *(Today: dropped, verified.)*
- **R6.** [BUG-2842] Changing the role to one this item already has on the formula (another line) → `add_formula_item` R8's refusal; nothing written.

**Errors:** `Formula item {id} not found` (404); role (422, internal); duplicate (422, BUG-2842). **Side effects:** sent fields, flushed.

---

## `ProductionFormulaManager.remove_formula_item(session, formula_item_id, workspace_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.remove_formula_item` ← `DELETE /production-formulas/items/{id}/`, 204)

**Purpose:** Take a line off a recipe.

**Returns:** the deleted `ProductionFormulaItem` object.

**Rules:**
- **R1.** A line not of this workspace → `Formula item {formula_item_id} not found`, nothing deleted (verified); a second remove of the same id → the same (verified for stages).
- **R2.** ✅ (D2) The row is deleted outright and flushed; later reads do not return it. The formula's state is not checked.

**Errors:** `Formula item {id} not found` (404). **Side effects:** row deleted, flushed.

---

## `ProductionFormulaManager.get_formula_items(session, formula_id, workspace_id, item_role=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaService.get_formula_items` ← `GET /production-formulas/{id}/items/?item_role=`; the query parameter has the role pattern)

**Purpose:** A recipe's lines, optionally of one role.

**Returns:** `list[ProductionFormulaItem]`.

**Rules:**
- **R1.** The formula must be of this workspace, else `Production formula {formula_id} not found` (verified). An inactive formula answers (✅).
- **R2.** `item_role` `None` or `""` (falsy) → every line of the formula with this workspace's `workspace_id` (verified: empty role → all). [BUG-1319] order `id` ascending.
- **R3.** A valid role → only lines of that role. [BUG-1320] order `id` ascending.
- **R4.** ✅ Lines of removed items are included (owner, 2026-11-02).
- **R5.** A non-empty role outside the four → `Invalid item_role …` [BUG-2844] (reachable from the manager only; the API's query pattern answers 422 first, ✅ D5).
- **R6.** Nothing is written.

**Errors:** formula not found (404); bad role (422). **Side effects:** none.

---

## `ProductionFormulaManager._validate_stage_refs(session, workspace_id, production_line_id, machine_id, expected_output_item_id)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `add_formula_stage`, `update_formula_stage`)

**Purpose:** Check a stage's line, machine and expected output item belong to the workspace.

**Returns:** `None`.

**Rules:**
- **R1.** A reference that is `None` is not checked.
- **R2.** A line not of this workspace → `Production line {id} not found` (verified: unknown). An inactive line is accepted (✅ line DAO Q1; verified).
- **R3.** [BUG-2840] A line whose factory is soft-deleted → `Production line {id} not found`. *(Today: accepted, verified.)*
- **R4.** A machine not of this workspace, or soft-deleted → `Machine {id} not found` (verified: unknown; deleted, via P8). An inactive machine (`is_active = False`, not deleted) is accepted.
- **R5.** An item unknown or of another workspace → `Item {id} not found` (verified: other workspace).
- **R6.** [BUG-2840] A removed item → `Item {id} not found`. *(Today: accepted, verified.)*
- **R6a.** *Pending OQ-F1.* Today a service item is accepted (verified); after the owner's answer, the expected output item follows the answer for recipe outputs (Claude, delegated 2026-11-19).
- **R7.** ✅ (D4) The references are checked separately; machine and line need not match. Order: line, machine, item; the first failure raises.
- **R8.** Nothing is written.

**Errors:** the three `… not found` messages, `ValueError` (404). **Side effects:** none.

---

## `ProductionFormulaManager.get_formula_stages(session, formula_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaService.get_formula_stages` ← `GET /production-formulas/{id}/stages/`)

**Rules:**
- **R1.** Formula not of this workspace → `Production formula {formula_id} not found` (verified); inactive formula answers (✅).
- **R2.** The formula's stages with this workspace's `workspace_id`, `stage_order` ascending (unique per formula, so stable); a stage row of another workspace is not returned.
- **R3.** Nothing is written.

**Errors:** formula not found (404). **Side effects:** none.

---

## `ProductionFormulaManager.add_formula_stage(session, stage_data, workspace_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.add_formula_stage` ← `POST /production-formulas/{formula_id}/stages/`; the endpoint first refuses a body `formula_id` different from the path, 422)

**Purpose:** Add a numbered stage to a recipe's route.

**Returns:** the new `ProductionFormulaStage`, flushed.

**Rules:**
- **R1.** Formula not of this workspace → `Production formula {formula_id} not found` (verified); an inactive formula is accepted (✅, verified).
- **R2.** References follow `_validate_stage_refs` R1–R8.
- **R3.** A `stage_order` already used by a stage of this formula (this workspace) → `Stage order {stage_order} already exists for this formula`, nothing written (verified).
- **R4.** [BUG-2843] A violation of `uq_formula_stage_order` (a lost race, or a hidden row of another workspace) surfaces as R3's refusal, and the session stays usable. *(Today: `IntegrityError`, verified; generic 409 at the API.)*
- **R5.** The row has the sent fields and `workspace_id` = the argument.
- **R6.** Check order: R1, R2, R3, then the insert.
- **R7.** [BUG-2845] (HR-1, schema) `name` stored trimmed; blank → 422. *(Today: `min_length=1` only.)*

**Errors:** formula / line / machine / item `not found` (404); stage order taken (422). **Side effects:** one `production_formula_stages` row, flushed.

---

## `ProductionFormulaManager.update_formula_stage(session, stage_id, stage_data, workspace_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.update_formula_stage` ← `PUT /production-formulas/stages/{id}/`)

**Returns:** the `ProductionFormulaStage`, flushed.

**Rules:**
- **R1.** A stage not of this workspace → `Formula stage {stage_id} not found` (verified).
- **R2.** A body with nothing left after dropping unset and `null` fields returns the stage untouched with no reference check (verified, even with a deleted machine stored).
- **R3.** [BUG-2841] Only references sent in the request (not `null`) are checked by `_validate_stage_refs`; stored ones are not re-checked. *(Today: the sent value or else the stored one is checked, so a stored deleted machine fails any edit, verified.)*
- **R4.** A sent `stage_order` different from the stored one, already used by another stage of the formula (this workspace) → `Stage order {n} already exists for this formula` (verified); the same value as stored is not checked (verified). ✅ (D6) a swap needs a spare number.
- **R5.** [BUG-2843] as `add_formula_stage` R4.
- **R6.** [BUG-2835] explicit `null` clears `production_line_id`, `machine_id`, `expected_duration_minutes`, `expected_output_quantity`, `expected_output_item_id`, `notes`; `null` for `name`, `stage_order` → 422. *(Today: dropped, verified.)*
- **R7.** `formula_id` cannot be changed. The formula's state is not checked.
- **R8.** Check order: R1, R2, R3, R4, then the write.
- **R9.** [BUG-2845] (HR-1) `name` trimmed; blank → 422.

**Errors:** stage / line / machine / item `not found` (404); stage order taken (422). **Side effects:** sent fields, flushed.

---

## `ProductionFormulaManager.remove_formula_stage(session, stage_id, workspace_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `ProductionFormulaService.remove_formula_stage` ← `DELETE /production-formulas/stages/{id}/`, 204)

**Returns:** the deleted `ProductionFormulaStage` object.

**Rules:**
- **R1.** A stage not of this workspace, or already removed → `Formula stage {stage_id} not found` (verified both).
- **R2.** ✅ (D2) The row is deleted and flushed. Batch stage logs seeded from it stay, with `formula_stage_id` set to `NULL` by the database and their `stage_name` kept.

**Errors:** `Formula stage {id} not found` (404). **Side effects:** row deleted; linked stage logs' `formula_stage_id` → `NULL`.

---

## `ProductionFormulaManager._clear_other_defaults(session, workspace_id, exclude_id=None)`
**Shape:** helper
**Persistence:** writes
**Visibility:** internal (used by: `create_formula`, `update_formula`)

**Purpose:** Keep at most one default formula per workspace.

**Rules:**
- **R1.** Every **active** formula of this workspace with `is_default = True` gets `is_default = False`, except `exclude_id`.
- **R2.** An inactive formula holding the flag is not touched (BUG-1329 / BUG-2837 stop new ones; verified today: the inactive default kept it).
- **R3.** Formulas of other workspaces are not touched.
- **R4.** `exclude_id` `None` → no exception; the formula with that id keeps its flag.
- **R5.** [BUG-2836] Each formula changed gets `updated_by` = the acting user. *(requires new parameter `user_id`; today: `updated_by` untouched, verified; `updated_at` moves by `onupdate`.)*
- **R6.** Each change is flushed; with no other default nothing is written.

**Errors:** none. **Side effects:** `is_default` (and `updated_at`) on other formulas.

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 65–71 | code exists in workspace | `create_formula` R1, R2 |
| 74–75 | `is_default` truthy → clear | `create_formula` R3, R4 |
| 98–100 | formula `None` | `update_formula` R1 |
| 101–104 | other workspace | `update_formula` R2 |
| 107 | `exclude_unset`, `exclude_none` | `update_formula` R3, R8, R9 |
| 108–109 | `is_default is True` → clear (exclude self) | `update_formula` R4, R5, R7 |
| 111 | `updated_by` always set | `update_formula` R8 |
| 121–123 | workspace-scoped read | `get_formula` R1, R2 |
| 134–141 | `active_only` | `get_formulas` R1–R3 |
| 151–157 | not found / other workspace | `delete_formula` R1, R2 |
| 158–159 | already inactive → return | `delete_formula` R4 |
| 161–163 | deactivate | `delete_formula` R3, R5 |
| 182–186 | formula not in workspace | `add_formula_item` R1 |
| 189–191 | item `None` | `add_formula_item` R2 |
| 192–195 | item other workspace | `add_formula_item` R3 (R5, R6 absent today) |
| 198–201 | role not in set | `add_formula_item` R7 |
| 203–206 | insert | `add_formula_item` R8, R9 |
| 216–220 | line not found | `update_formula_item` R1 |
| 222 | `exclude_none` | `update_formula_item` R3, R5 |
| 225–228 | role sent and invalid | `update_formula_item` R4 |
| 239–245 | not found / delete | `remove_formula_item` R1, R2 |
| 256–260 | formula not found | `get_formula_items` R1 |
| 262 | `item_role` truthy | `get_formula_items` R2, R3 |
| 263–266 | invalid role | `get_formula_items` R5 |
| 285–290 | line sent; not found | `_validate_stage_refs` R1, R2, R3 |
| 291–302 | machine sent; not found / deleted | `_validate_stage_refs` R1, R4 |
| 303–306 | item sent; missing or other workspace | `_validate_stage_refs` R1, R5, R6 |
| 311–318 | formula not found; list | `get_formula_stages` R1, R2 |
| 326–330 | formula not found | `add_formula_stage` R1 |
| 332–338 | references | `add_formula_stage` R2 |
| 340–344 | `stage_order` taken (loop: none / one / many) | `add_formula_stage` R3, R4 |
| 357–361 | stage not found | `update_formula_stage` R1 |
| 363–365 | empty dict → return | `update_formula_stage` R2 |
| 367–373 | references, sent or stored | `update_formula_stage` R3 |
| 375 | `stage_order` sent and changed | `update_formula_stage` R4 |
| 379–382 | sibling other than self has it | `update_formula_stage` R4, R5 |
| 389–394 | not found / delete | `remove_formula_stage` R1, R2 |
| 405–407 | active defaults of workspace | `_clear_other_defaults` R1–R3 |
| 409–410 | `exclude_id` truthy and matches → skip | `_clear_other_defaults` R4 |
| 411–412 | `f.is_default` (always true from the query) → clear | `_clear_other_defaults` R1, R5, R6 |
