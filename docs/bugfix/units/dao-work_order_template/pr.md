# fix(work_order_template): BUG-2330, BUG-2331, BUG-2332

Branch: `bugfix/dao-work_order_template` → `main`. Risk: `normal` (not trivial: BUG-2332 changes which drafts a plan-day run makes).

## Bugs

| ID | Title | Intended |
|---|---|---|
| BUG-2330 | Work order template list repeats and misses rows when timestamps tie | `WorkOrderTemplateDAO.get_by_workspace`: `created_at` descending, then `id` descending, before `skip` / `limit` (HR-6) |
| BUG-2331 | A template's default approvers have no order | `WorkOrderTemplateApproverDAO.get_by_template`: `id` ascending, the order they were chosen in (HR-6) |
| BUG-2332 | Plan-day run reaches templates through a deleted factory section | `list_recurring_due` (HR-4): a template whose default section is deleted is not chosen by a factory run; a section run naming a deleted section chooses nothing; templates with no section still match a factory run |

## The change

One file, `app/dao/work_order_template.py` (+11 / -4):

- The template list now sorts newest first and, for templates made at the same moment, highest id first, so paging can no longer show a template twice or skip one.
- A template's default approvers now come back in the order they were chosen (id ascending). Work orders made from a template receive their approvers in that order.
- The recurring-due query ignores deleted factory sections: a factory run no longer picks a template through its deleted default section, and a run naming a deleted section returns nothing. Template rows are not changed, so they match again when the section is restored.

The nine test markers for these three bugs are removed from `tests/unit/dao/test_work_order_template.py` (plus the three now-unused reason constants), and the three rows in `docs/testing/bugs.md` are marked `Fixed in bugfix/dao-work_order_template (PR pending)`.

## Impact (systems engineer, round 1: APPROVE)

Full review: `docs/bugfix/units/dao-work_order_template/impact-1.md`.

- Upstream: `WorkOrderTemplateManager.list_templates` (`GET /work-order-templates/`), `get_approvers` (`GET /work-order-templates/{id}/approvers/`), `WorkOrderManager.create_work_order_from_template` and `generate_drafts` (`POST /work-order-templates/generate-drafts/`, deprecated). No caller relies on the old order; approval logic uses `any` / `sum` / `len`, so approver order only changes the order of rows and history lines.
- `generate_drafts` factory run: a due template whose default section is deleted gets no draft and does not advance; existing drafts are untouched; after a restore it is overdue and picked on the next run (today's overdue behaviour).
- Query: the section-scope live-section subquery is uncorrelated; AND/OR grouping is correct; NULL sections behave as R4/R5a require; `0` inputs unchanged; workspace bound unchanged (the fix can only narrow results).
- Downstream: plain `SELECT`s, no locks / flush / commit.
- Database: no migration, constraint or index. No data-check script. Alembic has one head (`124_help_ticket_status`).

## Contract note

No contract change. Same fields, status codes and messages. Observable, as intended: ties in `GET /work-order-templates/` broken by id descending; approvers in chosen order; deprecated generate-drafts with `factory_id` makes no draft for a template whose default section is deleted. No frontend PR.

## Follow-up (not in this PR)

The systems engineer found that the manager's section fallback in `WorkOrderTemplateManager.generate_drafts` (`app/managers/work_order_template_manager.py`, around lines 248-256) takes every active template of the named section from `get_by_workspace` without looking at the section's `is_deleted`. So, seen from the endpoint, a section run naming a **deleted** section still makes drafts for that section's templates, even though `list_recurring_due` now returns nothing. To be logged as a new bug (pattern `join-ignores-soft-deleted`, manager file): "A section Plan-day run naming a deleted section still makes drafts for that section's templates (fallback ignores `is_deleted`); HR-4: chooses nothing, as in `list_recurring_due` R5a." Related: BUG-2345, BUG-2342, BUG-889.

## Flip check

**CLEAN**: 9 tests flipped as intended (8 xfailed → passed, plus WOTP-AG-09 xpassed → passed), 0 other changes. Full suite: 24423 tests, 18427 passed, 1 skipped, 5923 xfailed, 72 xpassed (the non-strict physical-order xfails may go either way). Compared against baseline `d5fea1c`. Result: `docs/bugfix/units/dao-work_order_template/flipcheck.json`.

Unit and caller tests: `tests/unit/dao/test_work_order_template.py`, `tests/unit/managers/test_work_order_template_manager.py`, `tests/unit/managers/test_work_order_manager.py`: 777 passed, 239 xfailed.

Note: the first flip-check run was rejected only by two legacy tests, `tests/test_attachments.py::test_derive_urls_authenticated_includes_signature` and `::test_derive_urls_raw_download_only`. They fail whenever `CLOUDINARY_*` env vars are unset: they patch `attachment_manager.settings`, but `cloudinary_client._ensure_configured` reads the core settings. They fail the same way in the main checkout with no fix applied, so this fix did not cause them. The baseline was recorded with those vars set, so the accepted run sets dummy values (`demo` / `123` / `secret`).

## Merge

Not trivial, so no auto-merge comment. The owner reviews and merges. GitHub CI runs when the PR is opened and must be green before merging.

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
