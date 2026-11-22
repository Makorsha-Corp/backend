# Production revamp: notes from the test sweep

On 2026-11-19 the owner said: "skip production, we have a big revamp that's gonna be done soon so we need to get that pulled in before we start testing. So just keep it as future work now alongside the other ones."

Production is **out of the test sweep** until the revamp lands. That covers these managers and services:
- `production_batch_manager` and `production_batch_service`
- `production_formula_manager` and `production_formula_service`
- `production_line_manager` and `production_line_service`

The three manager specs were drafted before the pause and are kept as reference, with status IN REVIEW (paused):
- `tests/unit/managers/production_batch_manager.spec.md`
- `tests/unit/managers/production_formula_manager.spec.md`
- `tests/unit/managers/production_line_manager.spec.md`

When the revamp is done, re-describe the new code from scratch and use these notes as a checklist.

The bug IDs below were provisional and are **not** in `docs/testing/bugs.md`. Treat them as findings against today's code.

Rules already set by the owner still apply to the revamp:
- **OQ-50:** production output cost stays manual for now (revisit after launch).
- **OQ-51 / BUG-2793:** stock becomes sellable through a "make sellable" move with linked ledger rows. Flipping a row that holds stock is refused.
- **BUG-2811:** a new product bucket records `avg_cost_before` as NULL.
- **HR-15:** money rounds half up.
- **HR-16:** no links across workspaces, ever.

## Design questions to settle for the revamp

These questions were drafted for the owner and never asked. The recommended answer is listed first in each.

**BQ1. Creating a batch directly as "in progress" or "completed".** Today no stock moves when this happens.
- (a) Every batch starts as a draft, then goes through Start (takes materials) and Complete (adds product).
- (b) Allow "record a past batch" on purpose. It does the same stock work as Start and Complete in one step, and refuses if storage is short.
- (c) Keep today's behaviour.

**BQ2. Cancelling a started batch.** Today its materials don't go back to storage.
- (a) The user confirms how much was really used (the default is none). The rest goes back to the storage it came from, at the cost it left with.
- (b) Always give everything back.
- (c) Keep today's behaviour.

**BQ3. Editing lines after Start.** Today stock never moves again; an input added after Start was never deducted.
- (a) Settle the difference at completion.
  - Removing a line after Start gives back what Start took for it.
  - Switching a line to or from "input" after Start is refused.
- (b) Freeze input lines once the batch has started.
- (c) Keep today's behaviour.

**BQ4. An input line with no quantity.** Today it is skipped silently at Start.
- (a) Refuse to start, and list the lines by item name.
- (b) Start anyway, with a warning.
- (c) Keep today's behaviour.

**BQ5. A single-output batch with no output line.** Today it puts nothing into finished goods at completion; the product only appears after "Post finished goods".
- (a) Always post at completion.
- (b) Keep a separate receipt step on purpose, for example after a quality check.
- (c) Keep today's mix.

**BQ6. The recipe-output fallback reads the recipe at posting time, not at Start.** So editing a recipe while a batch runs changes which item gets the stock.
- Either use the recipe as it was when the batch started,
- or lock a recipe's output lines while a batch on it is open.

**OQ-F1. Services can sit on a recipe as an input or an output.** Example: a batch of 500 whose only recipe output is "Dyeing fee" puts 500 sellable "Dyeing fee" into finished goods.
- (a) Refuse services on every recipe line.
- (b) Allow services as inputs only, for information; nothing is deducted.
- (c) Keep today's behaviour.

**O1. Moving a machine to another factory leaves its production line behind**, still pointing at the machine. Editing the line then fails.
- A. The line stays and lets go of the machine.
- B. The line moves with the machine. A batch in progress then splits between two factories.
- C. Refuse to move the machine while a line is attached.
- D. Keep today's behaviour.

## Findings in today's code

### Batches (provisional BUG-2812…2831)
- **Locks:**
  - Start, complete, cancel and "post finished goods" move stock without locking the batch row (HR-10).
  - Two batches created at once get the same number, and the second fails with a 500.
- **Storage check:** two input lines of the same item each pass the storage check on their own, so storage goes negative (6 + 6 taken from 10 leaves −2).
- **Cost:** an average price of 0.00 is recorded as "no cost" on Start consumption rows and on waste `total_cost`.
- **Messages:**
  - The "not enough stock" message names items by internal id.
  - Every error from `ProductionBatchService.create_batch` is a 422, including "not found". A missing production line in complete and post is also a 422.
- **Bad references:**
  - A removed item can be added to a batch.
  - A batch can be created on a line of a deleted factory.
  - A line can send stock to a deleted or unknown factory.
  - Location types other than storage and inventory are accepted and then silently ignored.
  - A stage log's `formula_stage_id` isn't checked, so it can point at another workspace's stage or another formula's stage (HR-16).
- **Formula changes:**
  - Changing a batch's formula accepts an inactive formula, though create refuses one.
  - The old formula's stage logs are kept.
  - The change is allowed after Start.
- **Lines:**
  - Only `create_batch` refuses an inactive line; start, complete and post don't check it.
  - "Post finished goods" ignores the lines' destinations, while completion honours them.
- **Editing:**
  - Edits to batches, lines and stage logs can't clear a field, because an explicit null is ignored.
  - An edit that changes nothing still stamps `updated_by` / `logged_by` (HR-9).
  - Deleting a draft batch records no `updated_by`.
  - Stage log names can be only spaces or keep their outer spaces (HR-1).
- **Notes:** completion and cancellation notes overwrite the batch's production notes.
- **Overflow:** an output of 10× the expected quantity or more overflows the percentage columns, and completion fails with a 500.
- **List and dashboard:**
  - The batch list applies only the first of several filters.
  - The dashboard's `total_count` equals the in-progress count.
- **Code clean-up:**
  - Dead code: `VALID_STATUSES` at `production_batch_manager.py:46`, and an empty `skipped` branch at lines 863–864.
  - The `start_batch` docstring says it creates batch items from the formula, but it doesn't.

### Formulas (provisional BUG-2832…2845)
- **Defaults:**
  - An inactive formula can be made the default, which takes the flag off the active default.
  - Formulas whose default flag is switched off by `_clear_other_defaults` get no `updated_by`.
- **Editing:**
  - `update_formula` stamps `updated_by` even when nothing changes.
  - Fields that can't be emptied: the formula's description and estimated time, a recipe line's unit and tolerance, and a stage's line, machine, expected values and notes.
  - Editing a stage re-checks references the edit doesn't touch, so a stage whose machine was deleted can't be renamed.
- **Bad references:**
  - A removed catalog item can be added to a recipe.
  - A stage accepts a removed item, or a line whose factory is deleted.
- **Recipe lines:** the same item can sit on one recipe twice in the same role.
- **Messages:**
  - A stage-number clash caught by the database gives the generic 409 instead of the specific message.
  - The "Invalid item_role" message lists the roles in a different order on each server run.
  - Any new formula error message must not contain "not found", or the service will answer with a 404.
- **Sort order:** the full formula list (without `active_only`) has none (HR-6).
- **Stage names:** a name of only spaces is accepted, and names keep their outer spaces (HR-1).

### Production lines (provisional BUG-2852…2861)
- **List:**
  - The plain line list has no sort order (HR-6).
  - It still shows lines of a deleted factory.
  - "Active only" is ignored when a factory is chosen.
- **Deleted factories and machines:**
  - A line of a deleted factory can still be opened by id.
  - A line can be created in a deleted factory.
  - A deleted machine can be attached to a line, on create and on update.
- **Editing:**
  - An edit can't detach the machine or clear the description.
  - An edit that changes nothing still stamps `updated_by` (HR-9).
  - Switching a line off through delete records no one.
- **Status codes:** a missing factory or machine is a 422 on create but a 404 on update, in `production_line_service`.

## For the other future features
- **Permissions:**
  - No role check anywhere in production. Any member can start, complete or cancel batches (which moves stock), post finished goods, edit recipes and stages, and create or switch off lines. Viewers and the ground team are included.
  - Suggestion: a "production supervisor" role for start, complete, cancel and post.
  - Recipe lines and stages record no author and no timestamp.
- **Notifications:** possible alerts for
  - a batch that can't start because materials are short;
  - a completed batch (finished goods are ready for sales);
  - a started batch that gets cancelled.
