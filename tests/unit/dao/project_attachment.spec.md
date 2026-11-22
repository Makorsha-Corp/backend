# Spec — `app/dao/project_attachment.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** **Delegated:** Q1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). It is not the owner's own answer. The DAO is dead code: nothing is left to test here, and no cases file follows from this spec. Same case as `tests/unit/dao/project_component_attachment.spec.md` Q1.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_proj.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; `get_by_project` and `get_link` answer `[]` / `None` on the empty table. **Read, not run:** no caller and no writer anywhere in `app/`, `tests/` or `scripts/` (searched for the DAO, the singleton, the model, the table name and the back-references `Project.attachments`, `Attachment.project_links`, `Profile.project_attachments`). **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | This DAO and its table are not used | remove the DAO; dropping the table is a separate migration | Claude, delegated |

The HR-6 points (`get_by_project` has no `ORDER BY`; `get_link` is `.first()` with no order and no unique constraint on the pair) fall away with the methods, so no bug is logged. If the table ever gets a writer, it needs an order ending in `id` and a unique constraint on `(project_id, attachment_id)`.

### New questions

### Q1. This DAO and its table are not used — ✅ remove
**Background:** Attachments reach their parent through the general table `attachment_links` (`entity_type`, `entity_id`); a project's files are links with `entity_type = project`. `project_attachments` is an older link table for projects only. Four of this DAO's six methods were already removed as dead code.
**What happens today:** `get_by_project` and `get_link` work when called directly (verified on the empty table), but nothing calls them and nothing in `app/` writes a row. The test database's table is empty.
**Example:** A project with three files has no row here; `GET /attachments/?entity_type=project&entity_id=…` reads `attachment_links`.
**Rules affected:** none left; the sections are removed
**Suggested answer:** `remove` — delete the DAO and its schemas' only use; dropping the model and table is a separate migration, after checking production has no rows. Alternative: `intended — keep`, if a use for the table is planned.
**Answer:** remove the DAO; dropping the table is a separate migration
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): dead code, to be removed. `get_by_project` and `get_link` moved to **Not specified**, listed in `docs/testing/dead-code-removal-checklist.md`. The model and table stay until that migration, after checking production has no rows; the model's back-references (`Project.attachments`, `Attachment.project_links`, `Profile.project_attachments`) go with it.

## Overview
`ProjectAttachmentDAO` has two reads of `project_attachments`, an old project ↔ attachment link table. It has no caller and is to be removed.

**Callables:** 0 specified · 3 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `project_attachments`):** `workspace_id`, `project_id`, `attachment_id` FK ON DELETE CASCADE, `attached_by` FK (no action), all NOT NULL; `attached_at` `timestamp` NOT NULL with database default `now()`. No unique constraint.

**Notes for the test designer:** no cases for this module.

## Not specified
- `ProjectAttachmentDAO.get_by_project` — dead code, to be removed (Claude, delegated).
- `ProjectAttachmentDAO.get_link` — dead code, to be removed (Claude, delegated).
- `project_attachment_dao` — module-level singleton, no logic; removed with the DAO.
- Inherited `BaseDAO` methods — no caller; covered by the base spec.
