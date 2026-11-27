# Impact review: dao-work_order_template, round 1 (2026-11-27)

Diff: `git -C E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-work_order_template diff origin/main -- app alembic`.
One file, `app/dao/work_order_template.py` (+11 / -4); nothing in `alembic/`.

- `WorkOrderTemplateDAO.get_by_workspace`: `ORDER BY created_at DESC` becomes `created_at DESC, id DESC`, still before `offset` / `limit` (BUG-2330, R5).
- `WorkOrderTemplateApproverDAO.get_by_template`: adds `ORDER BY id` ascending, one key (BUG-2331, R2).
- `WorkOrderTemplateDAO.list_recurring_due` (BUG-2332, R5a):
  - section scope: equality kept, plus `default_factory_section_id IN (SELECT id FROM factory_sections WHERE is_deleted = false)`;
  - factory scope: the outer join is unchanged; the match branch becomes `factory_id = :f AND factory_sections.is_deleted = false`; the `IS NULL` branch is unchanged.

## Query correctness (BUG-2332)

I compiled the query with both scopes (Postgres dialect, no DB):

```
FROM work_order_templates LEFT OUTER JOIN factory_sections ON ... default_factory_section_id = factory_sections.id
WHERE workspace_id = :w AND is_active = true AND is_recurring = true
  AND default_factory_section_id = :s
  AND default_factory_section_id IN (SELECT factory_sections.id FROM factory_sections WHERE factory_sections.is_deleted = false)
  AND (default_factory_section_id IS NULL OR factory_sections.factory_id = :f AND factory_sections.is_deleted = false)
```

- **The subquery is not correlated.** It keeps its own `FROM factory_sections` even though the outer query joins that table, so it does not collapse into the joined row. AND binds tighter than OR, so the factory branch groups correctly.
- **Both scopes (R6):** the result is `section = :s` AND :s is live AND :s is in factory :f. That is the AND of R4, R5 and R5a. Equality already drops NULL sections, so the `IS NULL` branch cannot let a no-section template through.
- **NULL sections:** section scope: `NULL = :s` and `NULL IN (...)` are both not true, so the template is excluded (R4, unchanged). Factory scope: the outer join keeps the row, and the `IS NULL` branch keeps it (R5a's "no section still matches"). The row's NULL `is_deleted` only appears in the other branch.
- **`is_deleted`** is `NOT NULL DEFAULT false` (`app/models/factory_section.py:27`), so `= false` never drops a live section with a NULL value.
- **`0` inputs (R5b):** `factory_section_id=0` → equality on 0 → `[]`. `factory_id=0` → only the `IS NULL` branch can match. Both unchanged.
- **Workspace (HR-16):** the template's `workspace_id` filter still bounds every result. The subquery of live section ids is not scoped to the workspace. That only matters for a template pointing at another workspace's section, which is invalid data under HR-16 (write side: BUG-1015). Before the fix such a template matched only if that foreign section's factory id equalled the run's factory id. Now it also has to be live, so the fix can only narrow it. No new leak. Not blocking.
- **Performance:** `IN (subquery)` on the PK and the outer join on the PK: trivial.

## Upstream

| Caller | Use | Effect |
|---|---|---|
| `WorkOrderTemplateManager.list_templates` (`app/managers/work_order_template_manager.py:113`) ← service ← `GET /work-order-templates/` | passes through | Tied rows come in a fixed order; pages neither repeat nor miss a row. |
| `WorkOrderTemplateManager.generate_drafts` (`:249`) section fallback, `get_by_workspace(is_active=True, limit=1000)` | filters in Python by section | Which 1000 templates survive the cap (BUG-2342) is now deterministic. Not fixed, but no longer random. No reliance on the old order. |
| `WorkOrderTemplateManager.get_approvers` (`:169`) ← `GET /work-order-templates/{id}/approvers/` (`endpoints/work_order_templates.py:216`) | passes through | Approvers in `id` order. |
| `WorkOrderManager.create_work_order_from_template` (`app/managers/work_order_manager.py:365`) via `get_approvers` | calls `add_approver` once per template approver | Same set of approvers. They are now added in `id` order, the order `_replace_approvers` inserted them (de-duplicated, chosen order). Each `add_approver` is independent (409 on duplicate, history entry per row), so only the order of the order's approver rows and history lines changes. No approval logic depends on the order: `_is_approved` uses `any`, and the counts use `sum`/`len`. |
| `WorkOrderTemplateManager.generate_drafts` (`:243`) ← `WorkOrderTemplateService.generate_drafts` ← `POST /work-order-templates/generate-drafts/` (deprecated) | `list_recurring_due` | See below. |

No other module calls `list_recurring_due` or uses `work_order_template_dao` / `work_order_template_approver_dao` (I grepped the instance names; the many `get_by_workspace` / `get_by_template` hits are other DAOs). The sheet / anchored-range paths (`WorkOrderManager._maybe_seed_template_recurrence`, `sync_recurrence_drafts_for_machine` → `generate_drafts_for_anchored_range`) work on one template by id and never call `list_recurring_due`. The recurrence re-pick logic is not touched. Return types, `[]` on no match, errors and keyword-only signatures are all unchanged.

### BUG-2332 through `generate_drafts`: fewer drafts, and what follows

- **Factory run (`factory_id` only):** this is where the fix bites. A due recurring template whose default section is deleted is no longer picked. So no drafts are made for it (before, `resolve_template_machine_ids` used the deleted section's machines), and `should_advance_template` is never reached, so its `next_generation_date` stays where it was.
  - **Existing drafts:** nothing deletes or edits work orders on this path. Drafts made earlier stay as they are.
  - **After a restore:** the template is overdue (R2), so the next run picks it and makes one draft for that run's `target_date`, then advances from `target_date`. Missed days are not back-filled. That is today's general overdue behaviour, not new. It matches the brief ("they match again if the section is restored").
  - **Response:** the 201 list is shorter. Same shape.
  - **Transactions:** a template that is not picked is not mutated, so there is no partial state. The service commit/rollback is unchanged.
- **Section run naming a deleted section (`factory_section_id`):** `list_recurring_due` now returns `[]`. But the manager's section fallback (`:248-256`) then takes **every** active template of that section from `get_by_workspace`, without looking at `is_deleted` and without a due check (BUG-2345, BUG-2342). The recurring templates the DAO dropped move from the "recurring" group into the fallback group. They still get drafts and still advance through `should_advance_template`. Seen from the endpoint, a section run on a deleted section is therefore almost unchanged. Two small differences: the order of the returned drafts (recurring first before, newest-first now), and a recurring template beyond the 1000 cap is now missed. The DAO rule (R5a) holds. The end-to-end intent, "a section run naming a deleted section chooses nothing", needs a manager fix (see Neighbouring bugs). That is outside this unit's scope (brief §5 and §6), so it does not block.
- **Section run naming a live section:** unchanged.
- **Both scopes:** templates of a deleted section are dropped from the recurring group. The section fallback only runs on the section id, so the same note applies if that section is the deleted one.

## Downstream

Plain `SELECT`s. No locks, flush or commit. A local import of `FactorySection` (the existing pattern). `id` is the PK. No effect on the transaction contract (TC1–TC6).

## API contract

No contract change. Same fields, status codes and messages. Observable:
- `GET /work-order-templates/`: ties broken by id (descending).
- `GET /work-order-templates/{id}/approvers/` and work orders made from a template: approvers in the order they were chosen.
- `POST /work-order-templates/generate-drafts/` (deprecated endpoint, kept but superseded by sheet anchoring) with `factory_id`: no drafts for templates whose default section is deleted.

This is the intended behaviour. The frontend needs nothing.

## Database

No migration, constraint or index. No check or repair script.

## Neighbouring bugs

- **BUG-2345 / BUG-2342** (manager `generate_drafts` section fallback): they make R5a's section half invisible at the endpoint (above). They don't clash, and their intended fixes don't conflict with this one. But neither intended text says the fallback must skip a **deleted** section's templates.
  - **Proposed new bug** for the planner, in the manager file, `join-ignores-soft-deleted`: "A section Plan-day run naming a deleted section still makes drafts for that section's templates (fallback ignores `is_deleted`); HR-4: chooses nothing, as in `list_recurring_due` R5a."
  - The orchestrator should log it (main-sweep range). I didn't edit `bugs.md`.
- **BUG-889** (`machine_dao.get_by_section` ignores a deleted section): when that is fixed, a deleted section yields no machines, which closes most of the gap above for templates without a default machine.
- **BUG-340 / BUG-341** (default machine): separate. A template with a default machine in a deleted section is now skipped on factory runs, which is consistent.
- **BUG-2341 / BUG-1015** (write side of deleted / foreign sections): untouched. They reduce how often this read-side case can arise.
- **BUG-2343** (locking): unaffected.

## BUG-2331 without approver rows (judged from code)

The fixer's DB check returned no rows, so its result proves nothing. From the code: `.order_by(WorkOrderTemplateApprover.id)` sits after both filters and before `.all()`, and it is ascending with one key. That matches R2 exactly and the pre-check's expectation (an `ORDER BY` with `.id`, no `DESC`, one key). The filters (template id and the row's own `workspace_id`, R1) are unchanged, and R3 (no membership / `is_active` check) still holds. The tester's run will cover the rows.

## Shortcuts / scope

None. Each change implements the rule as written, in the one method named. The `IN (subquery)` on the section scope is a reasonable way to avoid a second join of `factory_sections` when both scopes are given. The fixer said this up front. Nothing outside the three bugs changed. Raw-SQL ordering risk (improvement A11): none, all ORM columns.

## Risk tag

`normal` holds: one file, no migration, no contract change. BUG-2332 is not a trivial-list pattern, and it changes which drafts a run makes, so the PR should not be called trivial. It is not money, stock or security. It touches the planning flow, but no owner decision is needed: HR-4 plus the 2026-11-06 delegated decision settle it.

## Verdict

**APPROVE.** To the tester. Follow-up for the orchestrator: log the proposed manager bug above.
