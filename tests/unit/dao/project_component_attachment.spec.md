# Spec — `app/dao/project_component_attachment.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** Q1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-02). It is not the owner's own answer. The DAO is dead code: nothing is left to test here, and no cases file follows from this spec. The rules were removed; the Review keeps the record of why.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v3.py`, `v7.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; found; another workspace, component, attachment; a duplicate link with no ordering; a soft-deleted attachment; the argument forms. **Read, not run:** no caller and no writer anywhere in `app/` (searched for the DAO, the model and the table name). **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-02.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | This DAO and its table are not used | remove the DAO; dropping the table is a separate migration | Claude, delegated |

The HR-6 point on `get_link` (`.first()` with no order, no unique constraint) falls away with the method, so no bug is logged. If the table ever gets a writer, it needs `id` ascending and a unique constraint on the pair.

### New questions

### Q1. This DAO and its table are not used — ✅ remove
**Background:** Attachments reach their parent through the general table `attachment_links` (`entity_type`, `entity_id`), used for projects, components, orders and the rest. `project_component_attachments` is a second link table for components only. Four of this DAO's five methods were already removed as dead code.
**What happens today:** `get_link` works when called directly (verified), but nothing calls it, and nothing in `app/` writes a row. The test database's table is empty.
**Example:** A component with three photos has no row here: its links are in `attachment_links`, with `entity_type` `project_component`. `get_link` for any of them returns `None`.
**Rules affected:** none left; the section is removed
**Suggested answer:** `remove` — delete the DAO; dropping the model and table is a separate migration, after checking production has no rows. Alternative: `intended — keep`, if a use for the table is planned.
**Answer:** remove the DAO; dropping the table is a separate migration
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): dead code, to be removed. `get_link` moved to **Not specified**, listed in `docs/testing/dead-code-removal-checklist.md`. The model and table stay until that migration, after checking production has no rows.

## Overview
`ProjectComponentAttachmentDAO` has one read, of one link between a project component and an attachment. It has no caller and is to be removed.

**Callables:** 0 specified · 3 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `project_component_attachments`):** `workspace_id`, `project_component_id`, `attachment_id` FK CASCADE, `attached_by` FK (no action), all NOT NULL; `attached_at` NOT NULL with database default `now()`. No unique constraint.

**Notes for the test designer:** no cases for this module.

## Not specified
- `ProjectComponentAttachmentDAO.get_link` — dead code, to be removed (Claude, delegated).
- `project_component_attachment_dao` — module-level singleton, no logic; removed with the DAO.
- Inherited `BaseDAO` methods — no caller; covered by the base spec.
