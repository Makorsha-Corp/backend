# Spec — `app/managers/production_batch_manager.py`

> **Status:** PAUSED. Production is deferred until the revamp (owner 2026-11-19); see docs/future/production-revamp.md.
> **Source commit:** e48a092

> **Review round 2026-11-19 (describe, under the reviewer's delegation of 2026-11-19).** Every P and D item below was decided by Claude under the reviewer's delegation (2026-11-19) and is marked so; none of them is the owner's own answer. The house-rule lines stand. Questions about stock quantities and the production workflow are parked for the owner as **BQ1 … BQ5** (provisional labels; to be numbered OQ-n when added to `docs/testing/owner-questions.md`). Their rules are written to today's behaviour and marked *pending BQn*. Bug IDs BUG-2812 … BUG-2831 are **provisional** (merged into `docs/testing/bugs.md` later; not logged there yet).

> **Owner decisions applied, not asked again:** (1) **OQ-50** (owner 2026-11-17): production output carries no cost; finished goods cost is set by hand — revisit after launch. Here: `complete_batch` and `post_outputs_to_finished_goods` pass no unit cost, and waste is posted at the damaged bucket's existing average (or none). (2) **OQ-51 → BUG-2793**: production posts into the **not-for-sale** product bucket; making units sellable is `ProductManager.make_sellable` (new). Nothing in this manager changes for it. (3) **BUG-2811**: when an output creates a new product bucket, its ledger row records `avg_cost_before` NULL (`product_manager.spec.md` `apply_production_output` R8a); with no unit cost passed (OQ-50) today's NULL / NULL already matches. (4) **BUG-1330 / BUG-1331** (owner 2026-11-02): batches of a soft-deleted factory are hidden from lists (DAO), `get` stays raw, and a factory with `draft` / `in_progress` batches cannot be deleted. (5) **HR-15** money rounds half up; **HR-16** nothing links across workspaces.
>
> **Projects:** this manager has no project costing; nothing here is deferred under the 2026-11-10 projects decision.

> **Already logged, no new ID:** BUG-1321 (batch lists tie order, DAO), BUG-1322 / BUG-1323 (batch line order, DAO), BUG-1324 (a line's source / destination location of another workspace, HR-16), BUG-1022 (`add_batch_item` says "does not belong to workspace" for another workspace's item instead of "not found"), BUG-1330 (lists hide batches of a deleted factory), BUG-1333 / BUG-1334 (batch number after 999 / clock), BUG-2770 / BUG-2811 (`apply_production_output` lock / ledger before-value). The DAO specs' follow-ups are all answered below: `production_batch.spec.md` FU-1 (a)–(h), `production_batch_item.spec.md` FU-1 (a)–(e), `product_manager.spec.md` FU-3.

> **Verified PASS collaborators, referenced not restated:** `tests/unit/dao/production_batch.spec.md`, `production_batch_item.spec.md`, `production_batch_stage_log.spec.md`, `production_formula_stage.spec.md`, `production_formula_item.spec.md`, `production_line.spec.md`, `production_formula.spec.md`, `inventory.spec.md` (`get_by_factory_item_type` R1–R5, `ensure_for_factory_item_type` R1–R11, `sync_snapshot_from_ledger` R1–R12), `product_ledger.spec.md` (`exists_for_production_batch`), `base.spec.md` (`create` flushes, `update` sets every key that is an attribute and flushes, `remove` deletes and flushes). The finished-goods write is `tests/unit/managers/product_manager.spec.md` `apply_production_output` R1–R10 (APPROVED).

> **Verified by running** (my own script `v_batch_mgr.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddesc\batch\`, one outer transaction on `marker_test`, rolled back, nothing committed): `create_batch` with `status='completed'` accepted (`BATCH-2026-001`, status `completed`); two input lines of 6 on 10 in storage both deducted at start → storage **−2**, two `consumption` rows (10→4, 4→−2) with `unit_cost`, `total_cost`, `avg_price_before` all NULL on an average of 0.00; `cancel_batch` on that `in_progress` batch → `cancelled`, storage stays −2; shortfall message `Insufficient inventory for 1 input item(s): item_id=5992761 (required 5, available 3). Replenish storage before starting this batch.`; an input line with no quantity → start succeeds, nothing deducted; an input line added to an `in_progress` batch accepted, its role then changed to `output` accepted, and at completion that item was posted to finished goods (2 units, not-for-sale) although none was ever consumed; completion with actual 20 vs expected 1 → `DataError` numeric field overflow; actual 9 vs expected 1 → `output_variance_percentage 800.0`, `efficiency_percentage 900.0`; `post_outputs_to_finished_goods` after that completion → "already been posted"; `get_batches(production_line_id=…, status='in_progress')` returned completed, cancelled and draft batches; `get_batch_stats` → `{in_progress_count: 0, total_count: 0}` with 4 batches; `update_batch` with an empty body stamps `updated_by`. **Read, not run:** waste posting, destination overrides, stage logs, `post_outputs_to_finished_goods` fallback; `app/services/production_batch_service.py`; `app/api/v1/endpoints/production_batches.py` and `products.py` (`receive-from-batch`); the models and schemas named in the Overview. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs.

## Review
> All items except BQ1 … BQ5 are decided (house rule, precedent, or delegation). BQ1 … BQ5 wait for the owner; nothing else blocks the test designer, and the BQ rules are written to today's behaviour.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-10 | Start, complete, cancel and "post finished goods" read the batch with no lock, then move stock | bug (BUG-2812) | house rule |
| HR-9 | An edit that changes nothing still stamps `updated_by` (batch) / `logged_by` (stage log) | bug (BUG-2813) | house rule |
| HR-1 | A stage log name may be blank spaces or carry outer spaces | bug (BUG-2814) | house rule |
| HR-16 | A stage log can point at another workspace's (or another formula's) formula stage | bug (BUG-2815) | house rule |
| P1 | Two input lines of one item are checked against storage one by one, so storage goes negative | bug (BUG-2816) | Claude, delegated (BUG-2751 precedent) |
| P2 | An average price of 0.00 is recorded as "no cost" on the start and waste ledger rows | bug (BUG-2817) | Claude, delegated (BUG-707 precedent) |
| P3 | "Insufficient inventory" names items by internal id | bug (BUG-2818) | Claude, delegated (BUG-802 / BUG-2782 precedent) |
| P4 | A removed item can be added to a batch | bug (BUG-2819) | Claude, delegated (BUG-2780 precedent) |
| P5 | An edit cannot clear a field (batch, batch line, stage log) | bug (BUG-2820) | Claude, delegated (BUG-713 precedent) |
| P6 | A batch can be created on a line of a deleted factory, and a line can send stock to a deleted or unknown factory | bug (BUG-2821) | Claude, delegated (BUG-715 / BUG-684 precedent) |
| P7 | Two batches created at once can get the same number (500) | bug (BUG-2823) | Claude, delegated (BUG-2677 precedent) |
| D1 | Location types other than `storage` / `inventory` are accepted and silently ignored | bug (BUG-2822) | Claude, delegated |
| D2 | The batch list applies only the first of several filters | bug (BUG-2824) | Claude, delegated |
| D3 | The dashboard's "total batches" equals the in-progress count | bug (BUG-2825) | Claude, delegated |
| D4 | Deleting a draft batch records no `updated_by` | bug (BUG-2826) | Claude, delegated |
| D5 | Changing a batch's formula accepts an inactive formula (create refuses one) | bug (BUG-2827) | Claude, delegated |
| D6 | Changing a batch's formula keeps the old formula's stage logs | bug (BUG-2828) | Claude, delegated |
| D7 | A batch whose output is 10× the expected (or more) cannot be completed (500) | bug (BUG-2829) | Claude, delegated |
| D8 | "Post finished goods" ignores the lines' destinations; completion honours them | bug (BUG-2830) | Claude, delegated |
| D9 | Completion / cancellation notes overwrite the batch's production notes | bug (BUG-2831) | Claude, delegated |
| D10 | A batch on a line deactivated after it was planned can still be started | intended | Claude, delegated |
| D11 | Stage logs can be added and edited on completed and cancelled batches | intended | Claude, delegated |
| D12 | Percentages are rounded with Python's float `round` | intended (not money) | Claude, delegated |
| D13 | The unused `VALID_STATUSES` constant and the no-op `skipped` branch | remove | Claude, delegated |
| **BQ1** | **A batch can be created directly as "in progress" or "completed", skipping the stock moves** | _pending owner_ | owner |
| **BQ2** | **Cancelling a started batch does not give its materials back to storage** | _pending owner_ | owner |
| **BQ3** | **Changing a started batch's lines never moves stock again** | _pending owner_ | owner |
| **BQ4** | **An input line with no quantity is silently skipped when the batch starts** | _pending owner_ | owner |
| **BQ5** | **A single-output batch with no output line puts nothing in finished goods until someone presses "post finished goods"** | _pending owner_ | owner |

### House-rule violations — applied automatically

- **HR-10** `start_batch` R1, `complete_batch` R1, `cancel_batch` R1, `post_outputs_to_finished_goods` R1 — the batch is read with no row lock, its status (or "already posted") is checked, then stock moves. Two starts at once both deduct the inputs; two completes at once both post outputs and waste; a complete and a cancel at once leave a `cancelled` batch whose outputs are in finished goods; two "post finished goods" at once both pass the "already posted" check and post twice (stock quantities = real harm). Intended: the batch row is read `SELECT … FOR UPDATE` (a new `for_update` option on the read, default off), so the loser waits, then sees the new status and gets the normal "Can only …" / "already been posted" error.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2812 (pattern `hr-10-unlocked-state-transition`; answers `production_batch.spec.md` FU-1 (c)). Not unit-testable (two transactions); no case beyond "the locked read returns the same row".
- **HR-9** `update_batch` R7, `update_batch_stage_log` R7 — `updated_by` (batch) and `logged_by` (stage log, the "last logged by" stamp) are written on every call that reaches the write, even when every sent value equals the stored one (`update_batch` even on an empty body, verified). Intended: written only when at least one field actually changes value; otherwise the row is returned untouched.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-2813 (pattern `audit-stamp-on-noop`; answers `production_batch.spec.md` FU-1 (g), second half).
- **HR-1** `add_batch_stage_log` R6, `update_batch_stage_log` R6 — `stage_name` only needs 1 character (`min_length=1`): `"   "` is stored, `"  Dyeing "` keeps its spaces. Intended: `ProductionBatchStageLogCreate` / `Update` trim `stage_name` and refuse blank or whitespace-only (422).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2814 (pattern `blank-name-accepted`). Fix in `app/schemas/production_batch_stage_log.py`.
- **HR-16** `add_batch_stage_log` R5, `update_batch_stage_log` — `formula_stage_id` is stored as sent with no check: a stage of another workspace's formula is accepted (the foreign key exists globally). Intended: `formula_stage_id`, when sent, must be a stage of this workspace **and of the batch's own formula** (the second half decided by Claude under the reviewer's delegation, 2026-11-19: a stage log records a step of this batch's recipe); otherwise `ValueError("Formula stage {id} not found")` (404), nothing written. A batch with no formula accepts no `formula_stage_id`. (`ProductionBatchStageLogUpdate` has no `formula_stage_id`, so only `add` needs the check.)
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2815 (pattern `cross-workspace-link-not-refused`).

Checked and **not** a new line here: **HR-2** — no unique names (batch numbers are generated; BUG-1333 / BUG-2823). **HR-3** — `shift` is not grouped or filtered; location types are D1. **HR-4** — batches, lines and stage logs have no soft-delete column; `cancelled` is a state. A removed item is P4; a deleted factory P6. **HR-5 / HR-6 / HR-7** — lists filter in the query (D2 keeps it so); order is BUG-1321 / BUG-1322 / BUG-1323 at the DAO; stage logs are ordered `stage_order`, `id`; `GET /production-batches/` already bounds `limit`. **HR-8** — no `LIKE` on user text. **HR-11 – HR-14** — no externals, no sweeps. **HR-15** — the manager rounds no money: ledger `total_cost = avg_price × quantity` is computed unrounded and stored by `Numeric(15,2)`, which rounds half up; the percentages are not money (D12). **HR-16** — the line, formula and batch reads are scoped; locations are BUG-1324; the item message is BUG-1022; formula stages BUG-2815 (above).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-19)

### P1. Two input lines of one item are checked one by one, so storage goes negative — 🐞 BUG-2816
**Background:** Starting a batch checks each input line against the storage row of its item and factory, then deducts every line. Nothing stops two lines of one item. BUG-2751 ruled the same for return lines: repeats are added up and the total is checked.
**What happens today:** Each line is compared with the full storage quantity on its own. Verified: 6 + 6 on 10 both pass; storage ends at −2 with two `consumption` rows.
**Example:** A user adds "Cotton 600 kg" twice by mistake with 1,000 kg in storage. The batch starts, storage shows −200 kg, and the next purchase receipt is needed just to get back to zero.
**Rules affected:** `start_batch` R6
**Answer:** bug — per BUG-2751 precedent: input lines of the same item **and the same source factory** are added up and the total is checked against that storage row; short → the normal shortfall error with the total as `required`, nothing written. The lines stay separate (one ledger row each, as today).
**Resolution:** 🐞 BUG-2816 (pattern `repeated-line-bypasses-limit`).

### P2. An average price of 0.00 is recorded as "no cost" — 🐞 BUG-2817
**Background:** Ledger rows carry `unit_cost`, `total_cost` and before/after averages. BUG-707 ruled: a cost of 0 is a cost, so `total_cost` is 0.00, not empty.
**What happens today:** At start the code tests the average for truthiness: a storage row at 0.00 gives `unit_cost`, `total_cost`, `avg_price_before`, `avg_price_after` all NULL (verified), and a row with no average gives the same. At completion a waste row keeps `unit_cost` 0.00 but writes `total_cost` NULL.
**Example:** Free sample cotton booked at 0.00 is consumed: the ledger shows "—" for cost and for the average, as if the row had none.
**Rules affected:** `start_batch` R10, `complete_batch` R10a
**Answer:** bug — per BUG-707 precedent: when the storage / damaged row's average is not `None`, `unit_cost`, `avg_price_before`, `avg_price_after` are that average and `total_cost` = average × quantity (0 → 0.00); only an average of `None` gives NULL.
**Resolution:** 🐞 BUG-2817 (pattern `falsy-zero-treated-as-missing`).

### P3. "Insufficient inventory" names items by internal id — 🐞 BUG-2818
**Background:** The message reaches the user when "Start" is refused. BUG-802 / BUG-2782 ruled that user messages name what the user sees.
**What happens today:** `Insufficient inventory for 1 input item(s): item_id=5992761 (required 5, available 3). Replenish storage before starting this batch.` (verified).
**Example:** The production manager sees "item_id=57" and has to guess which material is short.
**Rules affected:** `start_batch` R7
**Answer:** bug — per BUG-2782 precedent: each shortfall reads `"{item name}" at {factory name} (required {n}, available {m})`; the rest of the text is unchanged. If the item or factory row cannot be read, fall back to `item {id}` / `factory {id}`.
**Resolution:** 🐞 BUG-2818 (pattern `internal-id-in-user-message`).

### P4. A removed item can be added to a batch — 🐞 BUG-2819
**Background:** An item is removed by `is_active = False`. BUG-2780 ruled that a removed item is "not found" for new stock rows. `production_batch_item.spec.md` FU-1 (a) flagged this.
**What happens today:** `add_batch_item` reads the item raw: a removed item is accepted (read, not run).
**Example:** "Old dye" was removed from the catalogue last month; a user adds it as an input and starting the batch deducts it from a storage row nobody sees in the item list.
**Rules affected:** `add_batch_item` R4
**Answer:** bug — per BUG-2780 precedent: a removed item → `ValueError("Item {item_id} not found")` (404), nothing written. Existing lines of a removed item stay and are posted as today.
**Resolution:** 🐞 BUG-2819 (pattern `unvalidated-foreign-key-reference`).

### P5. An edit cannot clear a field — 🐞 BUG-2820
**Background:** The three updates drop every field sent as `null` (`exclude_none`). BUG-713 ruled that explicit `null` clears an optional field.
**What happens today:** `{"notes": null}`, `{"formula_id": null}`, `{"actual_quantity": null}` → 200, old value kept.
**Example:** A user logs an actual quantity of 120 on the wrong line and empties it; the line still says 120 and completion uses it.
**Rules affected:** `update_batch` R3, `update_batch_item` R4, `update_batch_stage_log` R3
**Answer:** bug — per BUG-713 precedent: an explicit `null` clears every nullable column the update schema offers (batch: `formula_id`, `shift`, `expected_*`, `actual_*`, `actual_start_time`, `actual_end_time`, `notes`; line: `expected_quantity`, `actual_quantity`, the four location fields, `notes`; stage log: `production_line_id`, `started_at`, `completed_at`, the three quantities, `notes`); `null` for a NOT NULL column (`batch_date`, `status`, `item_role`, `stage_name`, `stage_order`, stage `status`) → 422; omitted fields unchanged. Clearing `formula_id` follows D6. Clearing a stage log's `output_quantity` while it is `completed` → the R7 error.
**Resolution:** 🐞 BUG-2820 (pattern `null-value-treated-as-absent`). Answers `production_batch.spec.md` FU-1 (g) first half and `production_batch_item.spec.md` FU-1 (d).

### P6. Batch work can point at a deleted or unknown factory — 🐞 BUG-2821
**Background:** A production line belongs to a factory; the line read is raw, so a line of a soft-deleted factory is found. BUG-1330 hides batches of a deleted factory from every list. A batch line's `source_location_id` / `destination_location_id` is a plain integer naming a factory (BUG-1324 covers another workspace's). BUG-715 / BUG-684 ruled that a soft-deleted factory is "not found" for new stock.
**What happens today:** (a) `create_batch` on a line of a soft-deleted factory → created, then hidden from every list at once. (b) A line with `destination_location_type 'inventory'` and a soft-deleted factory id posts finished goods or waste into that factory at completion; an id of no factory fails at completion with a foreign-key error (500).
**Example:** Factory 9 was deleted. A user plans `BATCH-2026-031` on its old line: 201, and the batch never appears on the batches page.
**Rules affected:** `create_batch` R2; `add_batch_item` R7; `update_batch_item` R5
**Answer:** bug — per BUG-715 precedent: (a) a line whose factory is soft-deleted → `ValueError("Production line {id} not found")`, nothing written; (b) `add_batch_item` / `update_batch_item` refuse a `source_location_id` (with type `storage`) or `destination_location_id` (with type `inventory`) that is not a live factory of this workspace → `ValueError("Factory {id} not found")` (404), nothing written (other workspace: BUG-1324, same message).
**Resolution:** 🐞 BUG-2821 (pattern `unvalidated-foreign-key-reference`).

### P7. Two batches created at once can get the same number — 🐞 BUG-2823
**Background:** The next number is the highest of the year + 1, read with no lock; the database allows each number once per workspace. BUG-2677 (work orders) ruled the same.
**What happens today:** Two creates at once both compute `BATCH-2026-015`; the second fails with a unique violation (500). (Read, not run; `production_batch.spec.md` FU-1 (e).)
**Example:** Two supervisors plan a batch in the same second; one of them gets "Internal server error".
**Rules affected:** `create_batch` R5
**Answer:** bug — per BUG-2677 precedent: the second create never answers 500; it gets the next free number (retry on the unique violation of `uq_batch_workspace_number`, or lock the workspace's numbering).
**Resolution:** 🐞 BUG-2823 (pattern `count-then-insert-race`). Not unit-testable (two transactions); a card may force a taken number and check the retry.

### Decided under delegation (2026-11-19)

### D1. Location types other than `storage` / `inventory` are silently ignored — 🐞 BUG-2822
**Background:** A batch line may name where its stock comes from (`source_location_type` / `_id`) and goes to (`destination_location_type` / `_id`). The model's comments list `storage`, `machine`, `inventory` for sources and `inventory`, `storage`, `damaged` for destinations; the schemas accept any text up to 50 characters.
**What happens today:** Only source `storage` and destination `inventory` (exact, lower case) with an id change anything. Every other value — `machine`, `Storage`, `damaged`, `storage` as a destination — is stored and ignored: the stock moves at the production line's factory.
**Example:** A user sets an input's source to "machine 4". Starting the batch deducts it from the line factory's storage, not from machine 4, with no message.
**Rules affected:** `add_batch_item` R7, `update_batch_item` R5; `start_batch` R5; `complete_batch` R11
**Answer:** bug — the schemas accept only what the code honours: `source_location_type` `null` or `'storage'`, `destination_location_type` `null` or `'inventory'` (422 otherwise); a type without an id, or an id without a type, → 422 (decided by Claude under the reviewer's delegation, 2026-11-19: refuse what cannot be done rather than move stock somewhere else silently; new location kinds come with their own posting code).
**Resolution:** 🐞 BUG-2822 (pattern `silently-ignored-input`). Fix in `app/schemas/production_batch_item.py`.

### D2. The batch list applies only the first filter — 🐞 BUG-2824
**Background:** `GET /production-batches/` takes `production_line_id`, `formula_id` and `status`.
**What happens today:** Only the first present one counts, in the order line → formula → status. Verified: line + `status=in_progress` returned completed, cancelled and draft batches.
**Example:** "In-progress batches on Line 2" shows every batch of Line 2.
**Rules affected:** `get_batches` R1
**Answer:** bug — every filter sent applies, combined with AND, in the query before paging (HR-5) (decided by Claude under the reviewer's delegation, 2026-11-19).
**Resolution:** 🐞 BUG-2824 (pattern `silently-ignored-input`; answers `production_batch.spec.md` FU-1 (a)). *(requires a combined DAO query)*

### D3. "Total batches" equals the in-progress count — 🐞 BUG-2825
**Background:** `GET /production-batches/stats/` feeds the dashboard's batch tiles.
**What happens today:** `total_count` is the in-progress count again (verified: 4 batches, `total_count` 0).
**Example:** The dashboard says "Total batches: 2" for a workspace with 40.
**Rules affected:** `get_batch_stats` R2
**Answer:** bug — `total_count` counts every batch of the workspace in any status, with the same `factory_id` filter and the same hiding of deleted factories (BUG-1330) as `in_progress_count` (decided by Claude under the reviewer's delegation, 2026-11-19).
**Resolution:** 🐞 BUG-2825 (pattern `wrong-aggregate`; answers `production_batch.spec.md` FU-1 (b)).

### D4. Deleting a draft batch records no `updated_by` — 🐞 BUG-2826
**Background:** "Delete" of a draft batch sets it `cancelled`; `cancel_batch` does the same and stamps `updated_by`.
**What happens today:** `delete_batch` writes only `status`; the last editor stays whoever edited before.
**Example:** The batch page shows "last changed by Rahim" on a batch Karim deleted.
**Rules affected:** `delete_batch` R3
**Answer:** bug — `updated_by` = the acting user *(requires new parameter `user_id`, passed by the service and endpoint)* (decided by Claude under the reviewer's delegation, 2026-11-19).
**Resolution:** 🐞 BUG-2826 (pattern `missing-audit-stamp`; answers `production_batch.spec.md` FU-1 (f)).

### D5. Changing a batch's formula accepts an inactive formula — 🐞 BUG-2827
**Background:** `create_batch` refuses an inactive formula ("is not active").
**What happens today:** `update_batch` checks only that the formula exists in the workspace.
**Example:** "Yarn v1" was retired; a user cannot create a batch with it but can switch an existing draft to it.
**Rules affected:** `update_batch` R5
**Answer:** bug — the same refusal as create: `ValueError("Production formula {id} is not active")` (422), nothing written (decided by Claude under the reviewer's delegation, 2026-11-19).
**Resolution:** 🐞 BUG-2827 (pattern `inconsistent-sibling-guard`).

### D6. Changing a batch's formula keeps the old formula's stage logs — 🐞 BUG-2828
**Background:** Creating a batch with a formula seeds one `pending` stage log per formula stage. Changing the formula later seeds nothing and removes nothing.
**What happens today:** A draft switched from "Yarn v1" (3 stages) to "Yarn v2" (4 stages) keeps v1's 3 stage logs and gets none of v2's; `update_batch` also accepts a formula change on an `in_progress` batch.
**Example:** The stage tracker of `BATCH-2026-020` shows "Carding, Spinning, Winding" although the batch now follows v2 with "Carding, Drawing, Spinning, Winding".
**Rules affected:** `update_batch` R5a
**Answer:** bug — (a) the formula can be changed (or cleared, P5) only while the batch is `draft`; on `in_progress` → `ValueError("Cannot change the formula of a started batch")` (422); (b) on a draft, the stage logs seeded from the old formula that are still untouched (`pending`, no quantities, no times) are deleted and the new formula's stages are seeded as `_seed_stage_logs_from_formula`; logs entered or edited by hand stay (decided by Claude under the reviewer's delegation, 2026-11-19: not stock, not money; the tracker must match the recipe).
**Resolution:** 🐞 BUG-2828 (pattern `stale-derived-rows`).

### D7. A batch whose output is 10× the expected cannot be completed — 🐞 BUG-2829
**Background:** `output_variance_percentage`, `efficiency_percentage` (batch) and `variance_percentage` (line) are `Numeric(5,2)`: at most 999.99.
**What happens today:** Efficiency ≥ 1000 % (actual ≥ 10 × expected) or variance ≥ 1000 % (≥ 11 ×) fails the flush with `DataError` (numeric field overflow); the whole completion rolls back and the user gets 500. Verified with actual 20 vs expected 1. The same for a line's variance.
**Example:** A batch planned for 1 test roll produces 12 rolls; "Complete" fails with "Internal server error" every time, and the batch can only be cancelled.
**Rules affected:** `complete_batch` R6; `_calculate_batch_item_variances` R3
**Answer:** bug — the three columns are widened to `Numeric(14,2)` (enough for any ratio of two Integer quantities), so completion never fails because of a percentage (decided by Claude under the reviewer's delegation, 2026-11-19: a display figure must not block stock posting). *(requires a migration)*
**Resolution:** 🐞 BUG-2829 (pattern `unbounded-decimal-input`; answers `production_batch.spec.md` FU-1 (h), `production_batch_item.spec.md` FU-1 (e)).

### D8. "Post finished goods" ignores the lines' destinations — 🐞 BUG-2830
**Background:** Completion posts each output / byproduct line to its destination factory when the line names one (`inventory` + id), else to the line's factory. "Post finished goods" (`/production-batches/{id}/post-finished-goods/` and `/products/receive-from-batch/{id}/`) posts the same lines, merged by item.
**What happens today:** "Post finished goods" always posts to the production line's factory, whatever the lines say.
**Example:** Output "Yarn" is set to go to Factory 2's finished goods. Through completion it lands in Factory 2; through "post finished goods" in Factory 1.
**Rules affected:** `post_outputs_to_finished_goods` R6
**Answer:** bug — the same destination rule as `complete_batch` R11; quantities are merged per (item, destination factory) (decided by Claude under the reviewer's delegation, 2026-11-19: one rule for where a batch's output goes; not a quantity change).
**Resolution:** 🐞 BUG-2830 (pattern `inconsistent-sibling-guard`).

### D9. Completion and cancellation notes overwrite the batch's notes — 🐞 BUG-2831
**Background:** A batch has one `notes` field for production notes. "Complete" and "Cancel" each take optional notes (completion notes / cancellation reason).
**What happens today:** Notes sent with complete or cancel replace the stored notes.
**Example:** The batch notes say "Moisture 9 %, machine 3 slow". The supervisor cancels with "Power cut"; the moisture note is gone.
**Rules affected:** `complete_batch` R4, `cancel_batch` R3
**Answer:** bug — the sent notes are appended: `{old notes}\n\n{label}: {sent notes}` with label `Completed` / `Cancelled`; with no old notes, just `{label}: {sent notes}`; `None` or `""` sent → notes unchanged (decided by Claude under the reviewer's delegation, 2026-11-19).
**Resolution:** 🐞 BUG-2831 (pattern `overwrite-instead-of-append`).

### D10. A batch on a line deactivated after it was planned can still be started — ✅ intended
**Background:** `create_batch` refuses an inactive line; `start_batch` and `complete_batch` read the line only for its factory. `production_line.spec.md` Q1: an inactive line is a normal, visible state that can be turned back.
**What happens today:** A draft planned on Line 2, then Line 2 deactivated: Start works.
**Example:** Line 2 is switched off for maintenance after tomorrow's batch was planned; the batch can still be started.
**Rules affected:** `start_batch` R2, `complete_batch` R2
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-19: deactivating a line stops new planning, not work already planned; the user can cancel the batch).

### D11. Stage logs can be added and edited on completed and cancelled batches — ✅ intended
**Background:** Batch lines refuse changes once a batch is completed or cancelled; stage logs do not check the batch's status. Stage logs move no stock.
**What happens today:** A stage log can be added to or edited on a batch in any status.
**Example:** The night supervisor enters the "Winding" stage record the morning after the batch was completed.
**Rules affected:** `add_batch_stage_log` R1, `update_batch_stage_log` R1
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-19: a stage log is a record; late entry is normal and harmless).

### D12. Percentages are rounded with Python's float `round` — ✅ intended
**Background:** Variance and efficiency percentages are computed in floating point and rounded to 2 places with `round`, which rounds ties to even on the float's binary value. HR-15 covers money only.
**What happens today:** A percentage whose third decimal is exactly 5 may round either way.
**Example:** No user-visible case short of 4-digit expected quantities; the figure is for display.
**Rules affected:** `complete_batch` R6, `_calculate_batch_item_variances` R2
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-19: not money). Tests use values without a tie at the third decimal.

### D13. Unused constant and no-op branch — 🗑️ remove
**Background:** `VALID_STATUSES` (line 46) is read nowhere in `app/`. In `_validate_stage_log_completion`, `if status == "skipped": return` (lines 863–864) is the last statement and changes nothing.
**What happens today:** No behaviour depends on either.
**Example:** Deleting them changes nothing a user can see.
**Rules affected:** none
**Answer:** remove (decided by Claude under the reviewer's delegation, 2026-11-19). For `docs/testing/dead-code-removal-checklist.md` (to be added by whoever merges this round): `app/managers/production_batch_manager.py:46` constant `ProductionBatchManager.VALID_STATUSES`; `app/managers/production_batch_manager.py:863-864` branch `skipped` no-op.

### OWNER questions — stock and production workflow (pending)

> Plain-language versions for the owner. Each has a recommended answer and what each option would mean in practice.

### BQ1. OWNER, stock / workflow — A batch can be created directly as "in progress" or "completed" — _pending_
**Background:** A batch is meant to move draft → in progress (Start takes the materials out of storage) → completed (Complete puts the product into finished goods). The create form's schema accepts a `status` field, and the code stores whatever is sent.
**What happens today:** `POST /production-batches/` with `status: "completed"` creates a completed batch (verified). Nothing was taken from storage and nothing was put into finished goods. "Post finished goods" then works on it, adding product without any material having been used. With `status: "in_progress"` the batch can be completed without its materials ever being deducted.
**Example:** Someone creates `BATCH-2026-040` as "completed" with an output line of 500 kg yarn, then presses "Post finished goods": 500 kg yarn appear in finished goods and the 550 kg of cotton it needs are still in storage.
**Rules affected:** `create_batch` R4 *(pending BQ1)*
**Recommended answer:** bug — a new batch is always created as draft; a `status` other than `draft` (or absent) is refused with 422, so stock only moves through Start and Complete.
**Options:**
- **(a) Recommended — always start as draft.** Every batch goes through Start (materials leave storage) and Complete (product enters finished goods), so stock always matches what was really made. Recording a batch that already happened means creating it, starting it and completing it in one sitting; it takes three clicks instead of one, but the books stay right.
- **(b) Allow "record a past batch" on purpose.** Keep the option to create a batch as completed, but make it do the work: creating it as completed takes the materials out and puts the product in, exactly as Start + Complete would, and refuses if storage is short. Convenient for back-entry, but it is a second path that must be kept identical to the normal one.
- **(c) Keep today's behaviour.** A batch created as completed or in progress moves no stock. Simple, but stock can be added to finished goods without materials being used, and nobody can tell from the batch that this happened.

### BQ2. OWNER, stock — Cancelling a started batch does not give its materials back — _pending_
**Background:** Starting a batch takes its input materials out of storage (a "consumption" line in the stock ledger). A started batch can be cancelled.
**What happens today:** Cancelling changes only the status. The materials stay deducted and no ledger line records a return (verified: storage stayed where Start left it).
**Example:** `BATCH-2026-022` started and took 800 kg of cotton out of storage. The spinning machine broke before any cotton was used, so the supervisor cancels the batch. Storage still shows the 800 kg as gone, although they are sitting on the floor, and someone has to correct storage by hand.
**Rules affected:** `cancel_batch` R4 *(pending BQ2)*
**Recommended answer:** bug — cancelling an in-progress batch asks how much of each material was actually used; the rest goes back to the storage it came from, with a ledger line linked to the batch. If nothing is entered, everything taken at Start goes back.
**Options:**
- **(a) Recommended — give back what was not used.** On cancel, the user confirms what was really used (default: nothing); the remainder returns to storage at the cost it left with, recorded against the batch. Storage stays true without manual fixes, and partly used material is still counted as used.
- **(b) Always give everything back.** Cancel returns every material taken at Start, in full. Simplest for the user, but if some material was already spoiled or used, storage shows more than is really there until someone corrects it.
- **(c) Keep today's behaviour.** Cancel gives nothing back; whoever cancels adjusts storage by hand. Nothing changes in the system, but storage is wrong after every cancelled batch until someone remembers to fix it.

### BQ3. OWNER, stock — Changing a started batch's lines never moves stock again — _pending_
**Background:** Start deducts each input line once, using its actual quantity if entered, else its expected quantity. After Start, lines can still be added, changed (quantity, role, source) or removed until the batch is completed. Completion posts only outputs, byproducts and waste.
**What happens today:** None of those changes touches storage. Verified: an input line added after Start was never deducted, and when its role was then changed to "output" it was posted into finished goods at completion although none of it had been used or made. Logging a higher actual usage after Start (110 kg instead of the 100 kg taken) leaves storage 10 kg too high; removing an input line never gives its material back.
**Example:** Start takes 100 kg of dye. During the run the operator uses 112 kg and records 112 on the line. Storage still shows only 100 kg used, so the next batch is planned against 12 kg of dye that does not exist.
**Rules affected:** `add_batch_item` R2, `update_batch_item` R2, `remove_batch_item` R2 *(pending BQ3)*
**Recommended answer:** bug — at completion, each input item is settled: the difference between what was finally recorded as used and what Start took is deducted (extra used) or returned (less used) with a ledger line linked to the batch; an input line removed after Start returns what Start took for it; changing a line's role away from or to "input" after Start is refused.
**Options:**
- **(a) Recommended — settle the difference at completion.** Start takes the planned amounts so nothing is double-booked during the run; at completion the system compares what was really used with what was taken and books the difference. Storage ends up exactly right and the operator can correct quantities freely while the batch runs.
- **(b) Freeze input lines once started.** After Start, input lines cannot be added, changed or removed; only outputs, byproducts and waste stay editable. Simple and safe, but real usage that differs from the plan can only be corrected with a manual storage adjustment.
- **(c) Keep today's behaviour.** Lines stay freely editable and storage only reflects what was taken at Start. Easy to use, but storage drifts from reality every time actual usage differs from the plan.

### BQ4. OWNER, stock — An input line with no quantity is skipped when the batch starts — _pending_
**Background:** An input line may be saved with neither an expected nor an actual quantity (both are optional).
**What happens today:** Start ignores such a line: it is not checked against storage and nothing is deducted (verified). The batch starts normally and shows the line as an input.
**Example:** A user adds "Cotton" as an input but forgets the quantity, and starts the batch. No cotton leaves storage, and at completion 500 kg of yarn are added to finished goods as if made from nothing.
**Rules affected:** `start_batch` R4 *(pending BQ4)*
**Recommended answer:** bug — Start is refused while any input line has no quantity, listing those lines by item name (`Enter a quantity for: "Cotton", "Dye"`); nothing is deducted.
**Options:**
- **(a) Recommended — refuse to start.** The user is told which input lines have no quantity and fixes them before starting. A forgotten quantity can never silently skip a deduction.
- **(b) Allow it, with a warning.** Start goes ahead but the response lists the inputs that were not deducted, so the screen can warn. Keeps placeholder lines possible, but relies on the user reading the warning.
- **(c) Keep today's behaviour.** A line with no quantity is treated as "nothing used". Placeholders are easy, but forgotten quantities pass unnoticed.

### BQ5. OWNER, stock — A single-output batch with no output line posts nothing until "post finished goods" — _pending_
**Background:** Completion puts output lines into finished goods. A batch can instead record its total output on the batch itself (`actual_output_quantity`) with no output line; when its formula has exactly one output item, a separate "Post finished goods" button posts that total. Each batch can be posted once (the button refuses after any finished-goods posting, including the one completion makes).
**What happens today:** Completing such a batch puts nothing into finished goods; the product appears only when someone presses "Post finished goods" afterwards. The batch response shows `finished_goods_posted: false` until then.
**Example:** `BATCH-2026-033` (formula "Yarn", one output) is completed with "actual output 480 kg" and no output line. Finished goods show no new yarn until the supervisor remembers the second button; meanwhile sales see none available.
**Rules affected:** `complete_batch` R12, `post_outputs_to_finished_goods` R8 *(pending BQ5)*
**Recommended answer:** bug — completion posts it too: when the batch has no output / byproduct line with a quantity, its `actual_output_quantity` is posted to the formula's single output item at completion, as the button does today; the button then has nothing left to do for such a batch.
**Options:**
- **(a) Recommended — post at completion.** Completing a batch always puts its product into finished goods, whichever way the output was recorded. One step, nothing forgotten.
- **(b) Keep the two steps on purpose.** Completion records production; a separate person confirms receipt into finished goods with the button (for example after a quality check). Useful if receipt is a real separate step, but finished goods lag until someone presses it.
- **(c) Keep today's behaviour but make it consistent.** Today, batches with output lines are posted at completion while single-output batches wait for the button; option (c) keeps that mix. It needs no change, but the same kind of batch behaves differently depending on how the output was typed in.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here.

| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **Production batch service** (`app/services/production_batch_service.py`, no spec yet) | (a) `create_batch` turns **every** `ValueError` into 422 `BusinessRuleError`, including "Production line {id} not found" / "Production formula {id} not found", where every other write maps "not found" to 404. (b) `complete_batch` / `post_outputs_to_finished_goods` map "not found" to 404 only when the text contains "production batch", so "Production line {id} not found" is 422 there. (c) `get_batch_items` and `get_batch_stage_logs` turn any `ValueError` of a read into 404 / 422 without rollback (TC6 holds). (d) `post_outputs_to_finished_goods` re-reads the batch after commit; TC1–TC6 otherwise as `base_service.spec.md`. | error mapping |
| FU-2 | **Permissions** — note for `docs/future/permissions.md` | Any workspace member can start, complete and cancel batches (moving storage and finished goods), post finished goods, and edit batch lines and stage logs; there is no role check. Candidates: "production supervisor" for start / complete / cancel / post; edit lines for production staff. | all writes |
| FU-3 | **Notifications** — note for `docs/future/notifications.md` | No one is told when a batch cannot start for lack of materials (P3 message), when a batch is completed (finished goods ready, relevant to sales), or when a started batch is cancelled. | `start_batch`, `complete_batch`, `cancel_batch` |
| FU-4 | **Calendar service** | Already `production_batch.spec.md` FU-3 (no new item). | — |

## Overview
`ProductionBatchManager` runs **production batches**: one production run on a production line, optionally following a formula, with lines for the items it consumes (`input`), makes (`output`, `byproduct`) and spoils (`waste`), and a per-stage log. It creates and edits batches and lines, moves a batch draft → in_progress → completed (or → cancelled), and does the stock moves: **Start** deducts every input line from factory storage (one `inventory_ledger` `consumption` row each); **Complete** computes variances and posts outputs / byproducts to finished goods (`ProductManager.apply_production_output`, not-for-sale bucket, no cost — OQ-50) and waste to the factory's damaged stock (`inventory_ledger` `damaged` row). **Post finished goods** is a separate, once-per-batch posting for completed batches. Callers: `ProductionBatchService` (commits; `ValueError` → 404 when the text contains "not found", else 422 — FU-1), reached through `/production-batches/…` and `POST /products/receive-from-batch/{id}/`. It never commits and takes no lock.

**Callables:** 20 specified · 2 not specified (+ class constants)
**Externals to mock:** `utcnow` (`app.utils.time.utcnow`, imported into this module: patch `app.managers.production_batch_manager.utcnow`) for `started_at` / `actual_start_time` / `completed_at` / `actual_end_time`. Model `created_at` / `updated_at` defaults also call `utcnow` (in `app.models.production_batch`, `…_stage_log`).
**Integration-only behavior:** the HTTP error mapping (FU-1); the endpoint's path / body `batch_id` mismatch check (422 `Path batch_id (…) does not match body batch_id (…)`) for lines and stage logs; two-transaction races (BUG-2812, BUG-2823).

**Model facts:**
- `production_batches`: `batch_number` String(50) NOT NULL, unique per workspace (`uq_batch_workspace_number`); `production_line_id` NOT NULL FK RESTRICT; `formula_id` FK SET NULL; `batch_date` Date NOT NULL; `shift` String(20); `status` String(20) NOT NULL default `'draft'`; `expected_output_quantity`, `expected_duration_minutes`, `actual_output_quantity`, `actual_duration_minutes`, `output_variance_quantity` Integer; `output_variance_percentage`, `efficiency_percentage` **Numeric(5,2)**; `actual_start_time`, `actual_end_time`, `started_at`, `completed_at` DateTime; `notes` Text; `created_by`, `updated_by`, `started_by`, `completed_by` FK profiles SET NULL; `created_at`, `updated_at` NOT NULL, Python default `utcnow`, `updated_at` `onupdate=utcnow`. No soft delete.
- `production_batch_items`: `batch_id` FK CASCADE; `item_id` FK RESTRICT; `item_role` String(20) NOT NULL; `expected_quantity`, `actual_quantity`, `variance_quantity` Integer; `variance_percentage` **Numeric(5,2)**; `source_location_type` / `destination_location_type` String(50), `source_location_id` / `destination_location_id` plain Integer (no FK); `notes`. No audit columns.
- `production_batch_stage_logs`: `production_batch_stage_log.spec.md` Model facts.
- `inventory` (storage / damaged rows): `qty` Integer NOT NULL (no check: may go negative), `avg_price` Numeric(15,2); one row per (workspace, item, type, factory) including deleted rows. `inventory_ledger`: `quantity`, `qty_before`, `qty_after` Integer NOT NULL; costs Numeric(15,2); `performed_at` database `now()`.

**Schemas** (Pydantic, checked before the manager):
- `ProductionBatchCreate`: `production_line_id` int, `batch_date` date (required); `formula_id` int|None; `shift` ≤ 20 chars; `status` default `'draft'`, pattern `draft|in_progress|completed|cancelled`; `expected_output_quantity`, `actual_output_quantity` > 0; `expected_duration_minutes`, `actual_duration_minutes` ≥ 0; `actual_start_time`, `actual_end_time`, `notes` optional.
- `ProductionBatchUpdate`: the same fields minus `production_line_id`, all optional default `None`.
- `ProductionBatchItemCreate`: `batch_id`, `item_id` int; `item_role` pattern `input|output|waste|byproduct`; `expected_quantity`, `actual_quantity` > 0 or `None`; location types ≤ 50 chars; ids int; `notes`. `ProductionBatchItemUpdate`: the same minus `batch_id`, `item_id`, all optional.
- `ProductionBatchStageLogCreate`: `batch_id` int, `formula_stage_id` int|None, `stage_name` 1–200 chars, `stage_order` ≥ 0 default 0, `production_line_id`, `status` default `'pending'` pattern `pending|in_progress|completed|skipped`, `started_at`, `completed_at`, `input_quantity` / `output_quantity` / `waste_quantity` ≥ 0, `notes`. `ProductionBatchStageLogUpdate`: the same minus `batch_id`, `formula_stage_id`, all optional.
- Endpoint bodies: Start `target_output_quantity` > 0; Complete `actual_output_quantity` > 0, `actual_duration_minutes` ≥ 0, `notes`; Cancel `notes`; Post `include_byproducts` default `True`. `GET /{id}/items/?item_role=` has the role pattern.

**Notes for the test designer:**
- `from app.managers.production_batch_manager import production_batch_manager`. Every error is `ValueError`; assert the message text.
- Parents: `Factory(workspace_id, name, abbreviation)`, `Item(workspace_id, name, name_normalized, unit)`, `ProductionLine(workspace_id, factory_id, name)`, `ProductionFormula(workspace_id, formula_code, name)`, `ProductionFormulaStage(workspace_id, formula_id, stage_order, name)`, `ProductionFormulaItem(workspace_id, formula_id, item_id, item_role, quantity)`, storage `Inventory(workspace_id, item_id, factory_id, inventory_type=InventoryTypeEnum.STORAGE, qty, avg_price)`. Profiles and workspaces from `tests/unit/factories.py`.
- The schemas refuse roles, statuses and quantities outside their patterns / bounds; to reach the manager's own checks (an odd role, a zero quantity), build the schema with `model_construct(...)` or store the row directly.
- Waste reads the damaged row through `ensure_for_factory_item_type`, which first aligns the row to its newest ledger entry (`inventory.spec.md` `sync_snapshot_from_ledger`): set up damaged rows **with** a matching ledger row, or expect the alignment.
- Batch numbers depend on the clock's year (BUG-1334); patch `app.dao.production_batch.datetime` as the DAO tests do, or assert only the `BATCH-` prefix shape.
- Calls that raise: wrap in `with db.begin_nested():`. A raised `DataError` (D7) needs that too.

## Not specified
- `ProductionBatchManager.__init__` — wires the batch, line, formula, formula-item, formula-stage and stage-log DAOs; no logic.
- `production_batch_manager` — module singleton.
- Class constants `VALID_STATUSES` (unused, D13 remove), `VALID_ITEM_ROLES`, `VALID_STAGE_LOG_STATUSES` — used by the rules below. Inherited `BaseManager` methods — `tests/unit/managers/base_manager.spec.md`; no caller uses them on this manager.

---

## `ProductionBatchManager.create_batch(session, batch_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ProductionBatchService.create_batch` → `POST /production-batches/`)

**Purpose:** Plan a new batch on a production line, optionally following a formula, and seed its stage logs from the formula.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `batch_data` | `ProductionBatchCreate` | See Schemas. |
| `workspace_id` | int | Line and formula must be of this workspace. |
| `user_id` | int | Stored as `created_by`; not checked. |

**Returns:** the new `ProductionBatch`, flushed, not committed.

**Rules:**
- **R1.** The production line must be a line of this workspace: unknown or another workspace's → `ValueError("Production line {id} not found")`; a line with `is_active = False` → `ValueError("Production line {id} is not active")`. Nothing written. Checked before the formula.
- **R2.** [BUG-2821] A line whose factory is soft-deleted → `ValueError("Production line {id} not found")`, nothing written. An inactive-but-live factory is accepted. *(Today: accepted; the batch is then hidden from every list by BUG-1330.)*
- **R3.** When `formula_id` is sent (not `None`): unknown or another workspace's → `ValueError("Production formula {id} not found")`; `is_active = False` → `ValueError("Production formula {id} is not active")`; nothing written. `formula_id` `None` → no formula check.
- **R4.** *(pending BQ1)* Every field of `batch_data` is stored as sent, **including `status`** (any of the four values), `expected_*`, `actual_*`, the two times and `notes`. A batch created as `in_progress` or `completed` has moved no stock (verified for `completed`). `workspace_id`, `created_by = user_id`; `updated_by`, `started_*`, `completed_*`, variance fields stay `NULL`; `created_at` / `updated_at` from `utcnow`.
- **R5.** `batch_number` = the next number of the workspace for the current year — `production_batch.spec.md` `generate_batch_number` (format `BATCH-{year}-{nnn}`, BUG-1333, BUG-1334). [BUG-2823] Two creates at once never answer 500: the second gets the next free number. *(Today: the second fails with `IntegrityError` on `uq_batch_workspace_number`.)* Not unit-testable as a race.
- **R6.** With a formula, one stage log per formula stage is created — `_seed_stage_logs_from_formula` R1–R4. Without a formula, none.
- **R7.** HR-16: a line or formula of another workspace is "not found" (R1, R3); the messages echo only the id sent.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| line missing / other workspace / deleted factory (BUG-2821) | `ValueError` | `Production line {id} not found` |
| line inactive | `ValueError` | `Production line {id} is not active` |
| formula missing / other workspace | `ValueError` | `Production formula {id} not found` |
| formula inactive | `ValueError` | `Production formula {id} is not active` |

**Side effects:** one `production_batches` row; stage-log rows (R6); flushed.

---

## `ProductionBatchManager.update_batch(session, batch_id, batch_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ProductionBatchService.update_batch` → `PUT /production-batches/{id}/`)

**Purpose:** Edit a draft or in-progress batch's plan, actuals and notes.

**Inputs:** `batch_data` — `ProductionBatchUpdate`; `user_id` → `updated_by`.

**Returns:** the batch, flushed.

**Rules:**
- **R1.** Unknown id or another workspace's batch → `ValueError("Production batch {id} not found")`.
- **R2.** A batch with status `completed` or `cancelled` → `ValueError("Cannot update a {status} batch")`, nothing written. `draft` and `in_progress` (and any other stored status) pass.
- **R3.** [BUG-2820] An explicit `null` clears the field (fields per P5); `null` for `batch_date` or `status` → 422; omitted fields unchanged. *(Today: every `null` is dropped; the old value stays.)*
- **R4.** A `status` sent with a value → `ValueError("Use start_batch, complete_batch, or cancel_batch to change status")`, nothing written — even when it equals the current status. Checked after R2.
- **R5.** A `formula_id` sent with a value must be a formula of this workspace, else `ValueError("Production formula {id} not found")`. [BUG-2827] An inactive formula → `ValueError("Production formula {id} is not active")`, nothing written. *(Today: an inactive formula is accepted.)*
- **R5a.** [BUG-2828] A change of `formula_id` (to another formula, or cleared after BUG-2820) is allowed only on a `draft`: on `in_progress` → `ValueError("Cannot change the formula of a started batch")`. On a draft, the old formula's untouched seeded stage logs (`status 'pending'`, all three quantities and both times `NULL`) are deleted and the new formula's stages seeded as `_seed_stage_logs_from_formula`; other stage logs stay. Sending the same `formula_id` as stored changes nothing. *(Today: any status; stage logs untouched.)*
- **R6.** Every other sent field is written as sent (any field of the schema: `batch_date`, `shift`, `expected_*`, `actual_*`, the two times, `notes`), on `draft` and `in_progress` alike.
- **R7.** [BUG-2813] (HR-9) `updated_by = user_id` only when at least one field changes value; otherwise the batch is returned untouched (`updated_at` unchanged). *(Today: written on every call that passes R1–R5, even an empty body — verified.)*
- **R8.** Order of checks: R1, R2, R4, R5 (then R5a), then the write.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace | `ValueError` | `Production batch {id} not found` |
| completed / cancelled | `ValueError` | `Cannot update a {status} batch` |
| status sent | `ValueError` | `Use start_batch, complete_batch, or cancel_batch to change status` |
| formula missing | `ValueError` | `Production formula {id} not found` |
| formula inactive (BUG-2827) | `ValueError` | `Production formula {id} is not active` |
| formula change after start (BUG-2828) | `ValueError` | `Cannot change the formula of a started batch` |

**Side effects:** the batch row's sent fields and `updated_by`; flushed.

---

## `ProductionBatchManager.get_batch(session, batch_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchService.get_batch` → `GET /production-batches/{id}/` (404 on `None`), `post_outputs_to_finished_goods` re-read)

**Rules:**
- **R1.** The batch of this workspace with that id, in any status, or `None` for an unknown id or another workspace's batch.
- **R2.** A batch of a soft-deleted factory is returned (the read stays raw, owner BUG-1330).

**Errors:** none. **Side effects:** none.

---

## `ProductionBatchManager.get_batches(session, workspace_id, production_line_id=None, formula_id=None, status=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /production-batches/`, which passes all five; `limit` 1–1000, `skip` ≥ 0 at the endpoint; `status` not validated there)

**Rules:**
- **R1.** [BUG-2824] Every filter sent applies (AND): line, formula and status together; no filter → every batch of the workspace. Filtering is in the query before `skip` / `limit`. *(Today: only the first present filter in the order line → formula → status applies; the others are ignored — verified.)*
- **R2.** Order, paging and the hiding of batches of a deleted factory follow the DAO: `production_batch.spec.md` `get_by_workspace` / `get_by_production_line` / `get_by_formula` / `get_by_status` (newest `batch_date` first, BUG-1321 tie order, BUG-1330 hiding). An unknown status → `[]`.
- **R3.** Only this workspace's batches; another workspace's line or formula id → `[]`.

**Errors:** none. **Side effects:** none.

---

## `ProductionBatchManager.get_batch_stats(session, workspace_id, factory_id=None)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `GET /production-batches/stats/`)

**Rules:**
- **R1.** `in_progress_count` = number of this workspace's `in_progress` batches, limited to batches whose line is in `factory_id` when given — `production_batch.spec.md` `count_by_status` (BUG-1330 hiding).
- **R2.** [BUG-2825] `total_count` = number of this workspace's batches in any status, with the same factory filter and hiding. *(Today: equals `in_progress_count` — verified.)*
- **R3.** Returns `{"in_progress_count": int, "total_count": int}`; 0 when nothing matches.

**Errors:** none. **Side effects:** none.

---

## `ProductionBatchManager.delete_batch(session, batch_id, workspace_id)`
**Shape:** state-transition (delete = cancel a draft)
**Persistence:** writes
**Visibility:** public (used by: `DELETE /production-batches/{id}/`)

**Rules:**
- **R1.** Unknown id / another workspace → `ValueError("Production batch {id} not found")`.
- **R2.** Status other than `draft` → `ValueError("Only draft batches can be deleted. Current status: {status}. Use cancel_batch for in-progress batches.")`, nothing written.
- **R3.** A draft becomes `cancelled`; the row stays; lines and stage logs stay; no stock moves (a draft has moved none). [BUG-2826] `updated_by` = the acting user *(requires new parameter `user_id`)*. *(Today: only `status` written.)*
- **R4.** Returns the batch, flushed.

**Errors:** see R1, R2. **Side effects:** `status` (+ `updated_at`).

---

## `ProductionBatchManager.start_batch(session, batch_id, workspace_id, user_id, target_output_quantity=None)`
**Shape:** state-transition (stock out)
**Persistence:** writes
**Visibility:** public (used by: `POST /production-batches/{id}/start/`)

**Purpose:** draft → in_progress, taking every input line's quantity out of factory storage; refused as a whole if any input is short.

**Inputs:** `target_output_quantity` — int > 0 at the endpoint, or `None`.

**Returns:** the batch, flushed.

**Rules:**
- **R1.** Unknown id / another workspace → `ValueError("Production batch {id} not found")`. Status other than `draft` → `ValueError("Can only start draft batches. Current status: {status}")`. [BUG-2812] (HR-10) The batch is read `FOR UPDATE`. *(Today: no lock.)*
- **R2.** ✅ (D10) The batch's line is read in the workspace for its factory (the **default source factory**); its `is_active` is not checked. A missing line → `ValueError("Production line {id} not found")` (invalid data only: the FK is RESTRICT).
- **R3.** A batch with no lines at all → `ValueError("Cannot start a batch with no items. Add at least one item before starting.")`. A batch with only output / waste / byproduct lines starts and deducts nothing.
- **R4.** *(pending BQ4)* Only lines with role exactly `input` are deducted. Each input's quantity is `actual_quantity` if truthy, else `expected_quantity`; when that is `None` or `0` the line is skipped: not checked, not deducted (verified for `None`; `0` cannot pass the schema).
- **R5.** Each input's source factory is `source_location_id` when `source_location_type == 'storage'` (exact) and the id is truthy; otherwise the default (R2). [BUG-2822] Only these values can be stored (D1). [BUG-1324 / BUG-2821] Only a live factory of this workspace can be stored as a source.
- **R6.** Availability: the source factory's live **storage** row of the item in this workspace (`inventory.spec.md` `get_by_factory_item_type` R1–R5); no row (or a soft-deleted one) → available 0. An input is short when available < quantity; exactly equal passes. [BUG-2816] Inputs of the same item and source factory are added up and the total is compared. *(Today: each line alone; 6 + 6 on 10 both pass and storage ends at −2 — verified.)*
- **R7.** Any short input → `ValueError("Insufficient inventory for {n} input item(s): {list}. Replenish storage before starting this batch.")`, `{list}` = one entry per short line joined by `"; "`. Nothing is written: no stock, no ledger, status stays `draft`. Every input is checked before anything is deducted. [BUG-2818] Each entry reads `"{item name}" at {factory name} (required {q}, available {a})`. *(Today: `item_id={id} (required {q}, available {a})` — verified.)*
- **R8.** When nothing is short, each counted input line (R4), in the order the lines are read (BUG-1322: `id` ascending), lowers its storage row's `qty` by its quantity (flushed), and writes one `inventory_ledger` row.
- **R9.** That ledger row: `workspace_id`, `inventory_type STORAGE`, `factory_id` = source factory, `item_id`, `transaction_type 'consumption'`, `quantity`, `qty_before` / `qty_after` (old / new `qty`), `source_type 'production_batch'`, `source_id` = batch id, `notes` = `SYSTEM - PRODUCTION BATCH START | {batch_number}`, `performed_by = user_id`, no transfer fields; `performed_at` database default.
- **R10.** [BUG-2817] Cost columns: when the storage row's `avg_price` is not `None`, `unit_cost`, `avg_price_before`, `avg_price_after` = `avg_price` (unchanged by the deduction) and `total_cost` = `avg_price × quantity`, stored at 2 places (half up by the column); `avg_price` `None` → all four NULL. *(Today: an average of 0.00 also gives all four NULL — verified.)* The storage row's `avg_price` is not changed.
- **R11.** Then the batch: `status 'in_progress'`, `started_by = user_id`, `started_at` = `actual_start_time` = `utcnow()` (the same value), `updated_by = user_id`; `expected_output_quantity` = `target_output_quantity` when not `None`, else unchanged. Nothing else is written: no lines are created from the formula and `expected_duration_minutes` is not set (the endpoint's description says otherwise; the code wins).
- **R12.** Order of checks: R1 (found, status), R2, R3, then R6–R7 for all inputs, then the writes.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace | `ValueError` | `Production batch {id} not found` |
| not draft | `ValueError` | `Can only start draft batches. Current status: {status}` |
| line missing | `ValueError` | `Production line {id} not found` |
| no lines | `ValueError` | `Cannot start a batch with no items. Add at least one item before starting.` |
| short | `ValueError` | `Insufficient inventory for {n} input item(s): …. Replenish storage before starting this batch.` |

**Side effects:** storage `qty` per counted input; one `consumption` ledger row each; batch status and stamps; flushed.

---

## `ProductionBatchManager.complete_batch(session, batch_id, workspace_id, user_id, actual_output_quantity=None, actual_duration_minutes=None, notes=None)`
**Shape:** state-transition (stock in)
**Persistence:** writes
**Visibility:** public (used by: `POST /production-batches/{id}/complete/`)

**Purpose:** in_progress → completed: record actuals, compute variances, post outputs / byproducts to finished goods and waste to damaged stock.

**Rules:**
- **R1.** Unknown id / another workspace → `ValueError("Production batch {id} not found")`; status other than `in_progress` → `ValueError("Can only complete in-progress batches. Current status: {status}")`. [BUG-2812] (HR-10) read `FOR UPDATE`. *(Today: no lock.)*
- **R2.** ✅ (D10) The line is read for its factory (default destination); missing → `ValueError("Production line {id} not found")`; `is_active` not checked.
- **R3.** The batch gets `status 'completed'`, `completed_by = user_id`, `completed_at` = `actual_end_time` = `utcnow()` (same value), `updated_by = user_id`; `actual_output_quantity` and `actual_duration_minutes` when not `None` (a `0` duration is written).
- **R4.** [BUG-2831] `notes` sent (not `None`, not `""`) is appended to the batch's notes as `{old}\n\nCompleted: {notes}` (no old notes → `Completed: {notes}`). *(Today: `notes` not `None` replaces the stored notes; `""` clears them.)*
- **R5.** Output variance uses `actual` = the sent `actual_output_quantity` if truthy, else the batch's stored one, and `expected` = the batch's `expected_output_quantity`. Only when both are not `None` and `expected > 0`: `output_variance_quantity = actual − expected`, `output_variance_percentage = round((actual − expected) / expected × 100, 2)`, `efficiency_percentage = round(actual / expected × 100, 2)` (as `Decimal`). Otherwise the three fields keep their stored values (normally `NULL`). Examples (verified): 9 vs 1 → 8, 800.00, 900.00; 90 vs 100 → −10, −10.00, 90.00.
- **R6.** [BUG-2829] Any percentage fits: completion succeeds for 20 vs 1 (efficiency 2000.00, variance 1900.00). *(Today: ≥ 1000.00 overflows `Numeric(5,2)` — `DataError`, verified; nothing is saved.)* ✅ (D12) Rounding is Python's float `round`; tests avoid ties at the third decimal.
- **R7.** Line variances are then computed — `_calculate_batch_item_variances` R1–R3.
- **R8.** Then every line of the batch (BUG-1322 order) is posted by its role, using quantity = `actual_quantity` if truthy, else `expected_quantity`; `None` or ≤ 0 → the line is skipped. Lines of role `input` (and any other stored role) post nothing here.
- **R9.** `output` and `byproduct` lines: `ProductManager.apply_production_output` with the destination factory (R11), `item_id`, quantity, `batch_id`, `user_id`, `notes` = `SYSTEM - PRODUCTION BATCH COMPLETE | {batch_number}`, no `unit_cost` — so the not-for-sale bucket's `qty` rises, its average is unchanged (OQ-50, revisit after launch; a new bucket's ledger row `avg_cost_before` NULL, BUG-2811), one `product_ledger` row `production` with `source_type 'production_batch'`, `source_id` = batch id (`product_manager.spec.md` `apply_production_output` R1–R10). Each line posts separately: two lines of one item give two product-ledger rows. Making the units sellable is OQ-51 / BUG-2793.
- **R10.** `waste` lines: the destination factory's **damaged** row of the item is found or created — `inventory.spec.md` `ensure_for_factory_item_type` R1–R11 (restored if soft-deleted; created with `qty 0`, `avg_price None`, `created_by = user_id`; then aligned to its newest ledger entry). Its `qty` rises by the quantity (flushed) and one `inventory_ledger` row is written: `inventory_type DAMAGED`, `factory_id` = destination, `item_id`, `transaction_type 'damaged'`, `quantity`, `qty_before` / `qty_after`, `unit_cost` = `avg_price_before` = `avg_price_after` = the damaged row's `avg_price` (may be `None`; unchanged — OQ-50, revisit after launch), `source_type 'production_batch'`, `source_id` = batch id, `notes` = the system note of R9, `performed_by = user_id`.
- **R10a.** [BUG-2817] Waste `total_cost` = `avg_price × quantity` whenever `avg_price` is not `None` (0.00 → 0.00). *(Today: 0.00 → NULL.)*
- **R11.** Destination factory = `destination_location_id` when `destination_location_type == 'inventory'` (exact) and the id is truthy; otherwise the line's factory (R2). [BUG-2822] / [BUG-1324] / [BUG-2821] only a live factory of this workspace with type `inventory` can be stored. *(Today: any type is stored and ignored; another workspace's or a deleted factory's id is posted into — verified for another workspace at the DAO; an unknown id fails with a foreign-key error.)*
- **R12.** *(pending BQ5)* The batch-level `actual_output_quantity` is **not** posted by completion; a batch with no output / byproduct line with a quantity puts nothing into finished goods here (see `post_outputs_to_finished_goods` R8).
- **R13.** Any error in R7–R11 (e.g. `DataError`, a foreign-key error) propagates; the service rolls everything back (TC3).
- **R14.** Returns the updated batch, flushed.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace | `ValueError` | `Production batch {id} not found` |
| not in progress | `ValueError` | `Can only complete in-progress batches. Current status: {status}` |
| line missing | `ValueError` | `Production line {id} not found` |
| percentage ≥ 1000 (today; BUG-2829) | `sqlalchemy.exc.DataError` | numeric field overflow |

**Side effects:** batch row; line variance fields; product buckets and product-ledger rows (R9); damaged rows and inventory-ledger rows (R10); flushed.

---

## `ProductionBatchManager.cancel_batch(session, batch_id, workspace_id, user_id, notes=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /production-batches/{id}/cancel/`)

**Rules:**
- **R1.** Unknown / another workspace → `ValueError("Production batch {id} not found")`; status not `draft` / `in_progress` → `ValueError("Can only cancel draft or in-progress batches. Current status: {status}")`. [BUG-2812] (HR-10) read `FOR UPDATE`. *(Today: no lock.)*
- **R2.** The batch gets `status 'cancelled'`, `updated_by = user_id`.
- **R3.** [BUG-2831] `notes` sent (not `None`, not `""`) is appended as `{old}\n\nCancelled: {notes}` (no old notes → `Cancelled: {notes}`). *(Today: `notes` not `None` replaces the stored notes.)*
- **R4.** *(pending BQ2)* No stock moves: for an `in_progress` batch the inputs taken at start stay deducted and no ledger row is written (verified). Lines and stage logs are untouched.
- **R5.** Returns the batch, flushed.

**Errors:** R1. **Side effects:** `status`, `updated_by`, maybe `notes`.

---

## `ProductionBatchManager.add_batch_item(session, item_data, workspace_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /production-batches/{id}/items/`; the endpoint first refuses a body `batch_id` different from the path's)

**Rules:**
- **R1.** The batch must be of this workspace: else `ValueError("Production batch {batch_id} not found")`. A `completed` or `cancelled` batch → `ValueError("Cannot add items to a {status} batch")`.
- **R2.** *(pending BQ3)* `draft` and `in_progress` batches accept new lines; a line added after start is never deducted (verified).
- **R3.** The item: unknown → `ValueError("Item {item_id} not found")`; another workspace's → refused, today with `ValueError("Item {item_id} does not belong to workspace {workspace_id}")` (422) — [BUG-1022] intended exactly `Item {item_id} not found`.
- **R4.** [BUG-2819] A removed item (`is_active = False`) → `ValueError("Item {item_id} not found")`, nothing written. *(Today: accepted.)*
- **R5.** `item_role` not one of `input`, `output`, `waste`, `byproduct` → `ValueError("Invalid item_role '{role}'. Must be one of: …")` (the list's order is not fixed — do not assert it). Reachable only past the schema (`model_construct`).
- **R6.** Order of checks: R1 (batch, status), R3–R4 (item), R5 (role).
- **R7.** Every field is stored as sent, plus `workspace_id`; the same item and role may appear several times. [BUG-2822] Location types limited (D1). [BUG-1324 / BUG-2821] A location id must be a live factory of this workspace, else `ValueError("Factory {id} not found")`. *(Today: any text and any integer stored.)*
- **R8.** Returns the new line, flushed.

**Errors:** R1, R3–R5, R7.

---

## `ProductionBatchManager.update_batch_item(session, batch_item_id, item_data, workspace_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PUT /production-batches/items/{id}/`)

**Rules:**
- **R1.** Unknown line / another workspace's → `ValueError("Batch item {id} not found")`. Its batch `completed` or `cancelled` → `ValueError("Cannot update items in a {status} batch")`. A line whose batch is not found in this workspace (invalid data, HR-16) skips the status check.
- **R2.** *(pending BQ3)* On `in_progress` batches every field can change — quantities, role (also to / from `input`), source — and no stock moves (verified: an input changed to `output` after start was then posted to finished goods at completion).
- **R3.** A sent `item_role` outside the four → `ValueError("Invalid item_role '{role}'. Must be one of: …")` (past the schema only).
- **R4.** [BUG-2820] Explicit `null` clears (P5). *(Today: `null` ignored.)*
- **R5.** Location rules as `add_batch_item` R7 (BUG-2822, BUG-1324, BUG-2821).
- **R6.** The sent fields are written; returns the line, flushed. No audit columns exist; an empty body flushes nothing new.

**Errors:** R1, R3, R5.

---

## `ProductionBatchManager.remove_batch_item(session, batch_item_id, workspace_id)`
**Shape:** delete (hard)
**Persistence:** writes
**Visibility:** public (used by: `DELETE /production-batches/items/{id}/`)

**Rules:**
- **R1.** Unknown / another workspace's → `ValueError("Batch item {id} not found")`; batch `completed` / `cancelled` → `ValueError("Cannot remove items from a {status} batch")` (skipped when the batch is not found in the workspace, as `update_batch_item` R1).
- **R2.** *(pending BQ3)* The row is deleted (gone from the table), on `draft` and `in_progress`; for an input of a started batch nothing goes back to storage.
- **R3.** Returns the deleted object, flushed.

**Errors:** R1.

---

## `ProductionBatchManager.get_batch_items(session, batch_id, workspace_id, item_role=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /production-batches/{id}/items/`; the endpoint already restricts `item_role` to the four roles)

**Rules:**
- **R1.** Unknown / another workspace's batch → `ValueError("Production batch {id} not found")`.
- **R2.** `item_role` falsy (`None`, `""`) → every line of the batch in this workspace; a role among the four → only those lines; any other → `ValueError("Invalid item_role '{role}'. Must be one of: …")`.
- **R3.** Order: `production_batch_item.spec.md` `get_by_batch` / `get_by_batch_and_role` (BUG-1322 / BUG-1323: `id` ascending). Lines of a removed item are included.

**Errors:** R1, R2. **Side effects:** none.

---

## `ProductionBatchManager._calculate_batch_item_variances(session, batch_id, workspace_id)`
**Shape:** compute
**Persistence:** writes
**Visibility:** internal (used by: `complete_batch`)

**Rules:**
- **R1.** For each line of the batch with `expected_quantity` not `None` and > 0 and `actual_quantity` not `None`: `variance_quantity = actual − expected`. Lines failing the condition are untouched (their variance fields keep their values).
- **R2.** `variance_percentage = round((actual − expected) / expected × 100, 2)` as `Decimal`. Example: expected 100, actual 112 → 12, 12.00; expected 3, actual 2 → −1, −33.33.
- **R3.** [BUG-2829] Any percentage fits (`Numeric(14,2)`). *(Today: ≥ 1000.00 → `DataError`, which fails the completion.)*
- **R4.** Every role is computed, inputs included. Flushed.

**Errors:** `DataError` today (R3). **Side effects:** line variance fields.

---

## `ProductionBatchManager.post_outputs_to_finished_goods(session, batch_id, workspace_id, user_id, *, include_byproducts=True)`
**Shape:** state-transition (stock in, once)
**Persistence:** writes
**Visibility:** public (used by: `POST /production-batches/{id}/post-finished-goods/` and `POST /products/receive-from-batch/{id}/`, both passing `include_byproducts` from the body, default `True`)

**Purpose:** Post a completed batch's output (and byproduct) quantities to finished goods, once.

**Returns:** the number of distinct items (after BUG-2830: item and destination pairs) posted.

**Rules:**
- **R1.** When any `product_ledger` row of this workspace has `source_type 'production_batch'` and `source_id` = this batch id → `ValueError("Finished goods for this batch have already been posted. Each batch can only be received into products once.")`, nothing written. Checked **first**, before the batch is read. Completion's own postings (`complete_batch` R9) count: after a completion that posted any output line, this always refuses (verified). [BUG-2812] (HR-10) the batch is read `FOR UPDATE` before this check, so two posts at once cannot both pass. *(Today: no lock.)*
- **R2.** Unknown / another workspace's batch → `ValueError("Production batch {id} not found")`; status other than `completed` → `ValueError("Only completed batches can post outputs to finished goods")`.
- **R3.** The line missing → `ValueError("Production line not found for this batch")`.
- **R4.** Roles posted: `output`, plus `byproduct` when `include_byproducts` is `True`.
- **R5.** For each line of those roles: quantity = `actual_quantity` when not `None`, else `expected_quantity` (unlike `complete_batch` R8, an `actual_quantity` of 0 stored directly is used, not replaced); `None` or ≤ 0 → skipped. Quantities are added up per item.
- **R6.** Destination: today always the line's factory, whatever the lines' destinations. [BUG-2830] The destination follows `complete_batch` R11, and quantities are added up per (item, destination factory). *(Today: the lines' destinations are ignored.)*
- **R7.** Each merged quantity is posted with `ProductManager.apply_production_output` (`unit_cost=None`, no notes → the ledger note is `SYSTEM - PRODUCTION BATCH COMPLETE | batch id {batch_id}`; OQ-50 no cost, revisit after launch; BUG-2811 for a new bucket).
- **R8.** *(pending BQ5)* Fallback: when no line gave a quantity, the batch's `actual_output_quantity` is truthy and > 0, the batch has a formula, and that formula has **exactly one** line of role `output` in this workspace (`production_formula_item.spec.md` `get_by_formula_and_role`) → that item gets the batch's `actual_output_quantity`, at the line's factory. Zero or several output items → no fallback. A deactivated formula or removed item still counts.
- **R9.** Nothing to post after R5–R8 → `ValueError("No quantities to post. Enter actual amounts on output/byproduct lines, or set actual output quantity on the batch when the formula has a single output item.")`, nothing written.
- **R10.** The batch row itself is not changed.
- **R11.** Check order: R1, R2 (found, status), R3, then R5–R9.

**Errors:** R1, R2, R3, R9.

**Side effects:** product buckets and product-ledger rows; flushed.

---

## `ProductionBatchManager._seed_stage_logs_from_formula(session, *, batch, formula_id, workspace_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** internal (used by: `create_batch`; after BUG-2828 also `update_batch`)

**Rules:**
- **R1.** One stage log per stage of the formula in this workspace, in `stage_order` ascending (`production_formula_stage.spec.md` `get_by_formula`); a formula with no stages → none.
- **R2.** Each log: `workspace_id`, `batch_id`, `formula_stage_id` = the stage's id, `stage_name` = the stage's name, `stage_order` = the stage's order, `status 'pending'`, `logged_by` `NULL`, quantities and times `NULL`.
- **R3.** `production_line_id` = the stage's own line when set, else the batch's line.
- **R4.** Flushed with the batch; not committed.

**Errors:** none.

---

## `ProductionBatchManager.get_batch_stage_logs(session, batch_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /production-batches/{id}/stage-logs/`)

**Rules:**
- **R1.** Unknown / another workspace's batch → `ValueError("Production batch {id} not found")`.
- **R2.** The batch's stage logs of this workspace, `stage_order` then `id` ascending (`production_batch_stage_log.spec.md` `get_by_batch`); none → `[]`.

---

## `ProductionBatchManager.add_batch_stage_log(session, log_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /production-batches/{id}/stage-logs/`; path / body `batch_id` mismatch refused at the endpoint)

**Rules:**
- **R1.** ✅ (D11) The batch must be of this workspace (else `ValueError("Production batch {batch_id} not found")`); its status is not checked.
- **R2.** A `status` outside `pending`, `in_progress`, `completed`, `skipped` → `ValueError("Invalid stage log status '{status}'")` (past the schema only).
- **R3.** A `production_line_id` sent must be a line of this workspace (active or not), else `ValueError("Production line {id} not found")`.
- **R4.** Completion requirement — `_validate_stage_log_completion` R1–R2.
- **R5.** [BUG-2815] (HR-16) A `formula_stage_id` sent must be a stage of this workspace and of the batch's formula, else `ValueError("Formula stage {id} not found")`. *(Today: stored as sent.)*
- **R6.** [BUG-2814] (HR-1) `stage_name` stored trimmed; blank → 422 at the schema. *(Today: as sent.)*
- **R7.** Every field stored as sent, plus `workspace_id` and `logged_by = user_id`; `started_at` / `completed_at` are not set from the status.
- **R8.** Check order: R1, R2, R3, R5, R4. Returns the log, flushed.

---

## `ProductionBatchManager.update_batch_stage_log(session, log_id, log_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PATCH /production-batches/stage-logs/{id}/`)

**Rules:**
- **R1.** ✅ (D11) Unknown log / another workspace's → `ValueError("Batch stage log {id} not found")`. The batch's status is not checked.
- **R2.** An empty update (nothing sent, or only `null`s today) returns the log untouched: no check, no write.
- **R3.** [BUG-2820] Explicit `null` clears (P5). *(Today: dropped.)*
- **R4.** The resulting status (sent, else stored) outside the four → `ValueError("Invalid stage log status '{status}'")` (reachable for a sent value past the schema, or a stored odd status).
- **R5.** A sent `production_line_id` must be a line of this workspace, else `ValueError("Production line {id} not found")`.
- **R6.** Completion requirement on the resulting status and `output_quantity` (sent, else stored) — `_validate_stage_log_completion`. [BUG-2814] `stage_name` trimmed, blank refused at the schema.
- **R7.** The sent fields are written. [BUG-2813] (HR-9) `logged_by = user_id` only when a field changes value. *(Today: on every non-empty update.)*
- **R8.** Check order: R1, R2, R4, R5, R6. Returns the log, flushed.

---

## `ProductionBatchManager._validate_stage_log_completion(status, output_quantity)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `add_batch_stage_log`, `update_batch_stage_log`)

**Rules:**
- **R1.** `status == 'completed'` and `output_quantity is None` → `ValueError("Completed stage logs require output_quantity")`. `output_quantity` 0 passes.
- **R2.** Every other status, with or without `output_quantity`, passes; returns `None`.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 83 | line not found | `create_batch` R1, R7 |
| 85 | line inactive | `create_batch` R1 |
| — | line's factory deleted (new) | `create_batch` R2 |
| 89 | `formula_id is not None` | `create_batch` R3 |
| 93, 95 | formula not found / inactive | `create_batch` R3 |
| 99 | batch number | `create_batch` R5 |
| 102–107 | stored as sent incl. status | `create_batch` R4 |
| 109 | seed when formula | `create_batch` R6 |
| 135 | batch not found | `update_batch` R1 |
| 137 | completed / cancelled | `update_batch` R2 |
| 140 | `exclude_none` | `update_batch` R3 |
| 143 | status sent | `update_batch` R4 |
| 147, 151 | formula sent / not found | `update_batch` R5, R5a |
| 154–155 | stamp + write | `update_batch` R6, R7 |
| 164 | get | `get_batch` R1, R2 |
| 179 / 184 / 189 / 194 | first filter wins / none | `get_batches` R1–R3 |
| 205–211 | stats | `get_batch_stats` R1–R3 |
| 228, 230 | not found / not draft | `delete_batch` R1, R2 |
| 236 | set cancelled | `delete_batch` R3 |
| 260, 262 | not found / not draft | `start_batch` R1 |
| 269 | line not found | `start_batch` R2 |
| 277 | no lines | `start_batch` R3 |
| 281 | inputs only | `start_batch` R4 |
| 285–287, 318–320 | `actual or expected`; skip falsy | `start_batch` R4 |
| 288–292, 321–325 | source factory | `start_batch` R5 |
| 297 | no storage row → 0 | `start_batch` R6 |
| 298 | short (`<`) | `start_batch` R6 |
| 305–313 | any short → raise | `start_batch` R7, R12 |
| 330–335 | deduct, flush | `start_batch` R8 |
| 332, 344–349 | avg `None` → 0; truthiness | `start_batch` R10 |
| 337–354 | ledger row | `start_batch` R9 |
| 356–364 | status, stamps; target | `start_batch` R11 |
| 390, 392 | not found / not in progress | `complete_batch` R1 |
| 399 | line not found | `complete_batch` R2 |
| 412, 414, 416 | optional actuals / notes | `complete_batch` R3, R4 |
| 420–422 | variance condition | `complete_batch` R5 |
| 423–431 | variance values | `complete_batch` R5, R6 |
| 435 | line variances | `complete_batch` R7 |
| 441–444 | loop, qty falsy / ≤ 0 skip | `complete_batch` R8 |
| 446–450 | destination | `complete_batch` R11 |
| 452 | output / byproduct | `complete_batch` R9 |
| 464 | waste | `complete_batch` R10 |
| (else) | input / other role | `complete_batch` R8 |
| 477, 489 | avg `None`; total truthiness | `complete_batch` R10, R10a |
| 516, 518 | not found / status | `cancel_batch` R1 |
| 527 | notes not `None` | `cancel_batch` R3 |
| 549, 551 | batch not found / closed | `add_batch_item` R1, R2 |
| 556, 558 | item missing / other workspace | `add_batch_item` R3 |
| 563 | role invalid | `add_batch_item` R5 |
| 568–571 | stored as sent | `add_batch_item` R7, R8 |
| 584 | line not found | `update_batch_item` R1 |
| 591 | batch found and closed | `update_batch_item` R1, R2 |
| 594 | `exclude_none` | `update_batch_item` R4 |
| 596 | role invalid | `update_batch_item` R3 |
| 613, 619 | not found / closed | `remove_batch_item` R1 |
| 622 | hard delete | `remove_batch_item` R2, R3 |
| 635 | batch not found | `get_batch_items` R1 |
| 638–645 | role truthy / invalid / filter | `get_batch_items` R2 |
| 647 | all lines | `get_batch_items` R2, R3 |
| 663–664 | loop; expected > 0 and actual set | `_calculate_batch_item_variances` R1, R4 |
| 665–670 | values | `_calculate_batch_item_variances` R2, R3 |
| 689 | already posted | `post_outputs_to_finished_goods` R1 |
| 700, 702 | not found / not completed | `post_outputs_to_finished_goods` R2 |
| 708 | line not found | `post_outputs_to_finished_goods` R3 |
| 713 | include byproducts | `post_outputs_to_finished_goods` R4 |
| 721 | role not posted | `post_outputs_to_finished_goods` R4 |
| 723–726 | `is not None`; skip ≤ 0; merge | `post_outputs_to_finished_goods` R5, R6 |
| 728 | fallback condition | `post_outputs_to_finished_goods` R8 |
| 735 | exactly one output | `post_outputs_to_finished_goods` R8 |
| 738 | nothing to post | `post_outputs_to_finished_goods` R9 |
| 744–756 | post each; count | `post_outputs_to_finished_goods` R7, Returns |
| 771 | loop stages | `_seed_stage_logs_from_formula` R1 |
| 778 | stage line or batch line | `_seed_stage_logs_from_formula` R3 |
| 789 | batch not found | `get_batch_stage_logs` R1 |
| 805 | batch not found | `add_batch_stage_log` R1 |
| 808 | status invalid | `add_batch_stage_log` R2 |
| 811, 815 | line sent / not found | `add_batch_stage_log` R3 |
| 818 | completion check | `add_batch_stage_log` R4 |
| 820–823 | stored, `logged_by` | `add_batch_stage_log` R7 |
| 836 | log not found | `update_batch_stage_log` R1 |
| 840 | empty update | `update_batch_stage_log` R2 |
| 843–845 | resulting status invalid | `update_batch_stage_log` R4 |
| 847, 851 | line sent / not found | `update_batch_stage_log` R5 |
| 854–855 | completion check | `update_batch_stage_log` R6 |
| 857–858 | stamp, write | `update_batch_stage_log` R7 |
| 861 | completed without output | `_validate_stage_log_completion` R1 |
| 863–864 | skipped no-op (D13 remove) | `_validate_stage_log_completion` R2 |

## Bugs found while reading (provisional IDs — to be merged into `docs/testing/bugs.md`)
| ID | Pattern | Where | Title | Today | Intended | Spec |
|---|---|---|---|---|---|---|
| BUG-2812 | `hr-10-unlocked-state-transition` | `start_batch`, `complete_batch`, `cancel_batch`, `post_outputs_to_finished_goods` | Batch stock moves read the batch without a lock | Two starts / completes / posts at once both move stock; complete + cancel leave a cancelled batch with posted outputs | Batch read `FOR UPDATE`; the loser gets the normal state / "already posted" error (HR-10) | HR-10 line |
| BUG-2813 | `audit-stamp-on-noop` | `update_batch`, `update_batch_stage_log` | No-op edit stamps `updated_by` / `logged_by` | Written on every call (verified for an empty batch update) | Only when a field changes (HR-9) | HR-9 line |
| BUG-2814 | `blank-name-accepted` | `app/schemas/production_batch_stage_log.py` | Stage log name may be blank spaces | `"   "` stored; outer spaces kept | Trimmed; blank → 422 (HR-1) | HR-1 line |
| BUG-2815 | `cross-workspace-link-not-refused` | `add_batch_stage_log` | Stage log can point at another workspace's or another formula's stage | `formula_stage_id` stored unchecked | Must be a stage of this workspace and the batch's formula; else 404 `Formula stage {id} not found` (HR-16) | HR-16 line |
| BUG-2816 | `repeated-line-bypasses-limit` | `start_batch` | Two input lines of one item each pass the storage check, storage goes negative | 6 + 6 on 10 → −2 (verified) | Same item + source summed and checked (BUG-2751) | P1 |
| BUG-2817 | `falsy-zero-treated-as-missing` | `start_batch`, `complete_batch` (waste) | Zero average price recorded as no cost | Start: 0.00 → cost and averages NULL (verified); waste: `total_cost` NULL | Not-`None` average used; 0 → 0.00 (BUG-707) | P2 |
| BUG-2818 | `internal-id-in-user-message` | `start_batch` | Shortfall message names items by internal id | `item_id=5992761 (required 5, available 3)` (verified) | `"{item}" at {factory} (required …, available …)` (BUG-2782) | P3 |
| BUG-2819 | `unvalidated-foreign-key-reference` | `add_batch_item` | Removed item can be added to a batch | Accepted | 404 `Item {id} not found` (BUG-2780) | P4 |
| BUG-2820 | `null-value-treated-as-absent` | `update_batch`, `update_batch_item`, `update_batch_stage_log` | Edits cannot clear a field | `null` ignored | `null` clears nullable fields; NOT NULL → 422 (BUG-713) | P5 |
| BUG-2821 | `unvalidated-foreign-key-reference` | `create_batch`; `add_batch_item` / `update_batch_item` locations | Batch on a deleted factory's line; line locations to a deleted or unknown factory | Accepted; posting into a deleted factory, or FK error 500 | 404 `Production line {id} not found` / `Factory {id} not found` (BUG-715) | P6 |
| BUG-2822 | `silently-ignored-input` | `app/schemas/production_batch_item.py` | Location types other than `storage` / `inventory` silently ignored | Stored; stock moves at the line's factory | Only `storage` (source) / `inventory` (destination) or null; type and id together; else 422 | D1 |
| BUG-2823 | `count-then-insert-race` | `create_batch` (+ `generate_batch_number`) | Two batches created at once get the same number | Second → `IntegrityError` 500 | Next free number, never 500 (BUG-2677) | P7 |
| BUG-2824 | `silently-ignored-input` | `get_batches` (+ DAO) | Batch list applies only the first filter | Line + status returns every status (verified) | All filters AND, in the query | D2 |
| BUG-2825 | `wrong-aggregate` | `get_batch_stats` | "Total batches" equals the in-progress count | `total_count = in_progress_count` (verified) | Every batch, same factory filter and hiding | D3 |
| BUG-2826 | `missing-audit-stamp` | `delete_batch` | Deleting a draft records no `updated_by` | Only `status` written | `updated_by` = acting user (new `user_id` parameter) | D4 |
| BUG-2827 | `inconsistent-sibling-guard` | `update_batch` | Formula change accepts an inactive formula | Accepted | 422 `Production formula {id} is not active`, as create | D5 |
| BUG-2828 | `stale-derived-rows` | `update_batch` | Formula change keeps the old formula's stage logs | Old logs kept, new stages not seeded; allowed after start | Draft only; untouched seeded logs replaced by the new formula's | D6 |
| BUG-2829 | `unbounded-decimal-input` | `complete_batch`, `_calculate_batch_item_variances` (+ migration) | Output 10× expected (or more) cannot be completed | `Numeric(5,2)` overflow → 500 (verified) | Columns `Numeric(14,2)`; completion never fails on a percentage | D7 |
| BUG-2830 | `inconsistent-sibling-guard` | `post_outputs_to_finished_goods` | "Post finished goods" ignores line destinations | Always the line's factory | Same destination rule as `complete_batch`; merged per item + destination | D8 |
| BUG-2831 | `overwrite-instead-of-append` | `complete_batch`, `cancel_batch` | Completion / cancellation notes overwrite production notes | Replaced | Appended with `Completed:` / `Cancelled:` label | D9 |
