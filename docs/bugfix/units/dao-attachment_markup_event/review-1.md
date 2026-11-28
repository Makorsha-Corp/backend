# Code review 1: dao-attachment_markup_event (2026-11-28)
Verdict: PASS   (blockers: 0, majors: 0, minors: 0, nits: 1)
Diff reviewed: 092776b..af94ef0, files: app/dao/attachment_markup_event.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- BUG-1436 (HR-6, BUG-1321 precedent): `list_for_attachment` orders by
  `created_at DESC, id DESC` in SQL. Entries with the same time come back
  highest `id` first, and an update to a row must not change that.
- BUG-1437 (BUG-982 precedent): the `limit` parameter and its `.limit(...)`
  call both go, so every matching row is returned (201 gives 201, 260 gives
  260). No paging is added anywhere. The only caller,
  `AttachmentMarkupManager.list_events`, never passed `limit`, so no caller
  needs to change.
- Must not change: the `workspace_id` and `attachment_id` filters (HR-16,
  R1/R2), keyword-only parameters after `db`, the `list` return type,
  `create_event`, the module singleton, the soft-delete behaviour (R5: no
  attachment-state filter), and no schema or migration.
- Edge cases: an empty history, unknown attachment id or `0` gives `[]`,
  another workspace's rows give `[]`, all rows tied on one time, more than
  200 rows.

## 2. Findings

No blockers, majors or minors.

What I checked:
- **Diff vs expectation:** it matches item for item. The order is
  `created_at.desc(), id.desc()`, and both `limit` and `.limit()` are gone.
  The filters, signature style, `create_event` and the singleton are
  unchanged.
- **Callers:** `grep list_for_attachment` over `app/ scripts/ alembic/` finds
  only `app/managers/attachment_markup_manager.py:337`, which passes only
  `workspace_id` and `attachment_id`. Removing the parameter breaks nothing.
- **Consistency:** the ordering style matches the established tie-break
  pattern, e.g. `app/dao/help_ticket.py:119` and
  `app/dao/attachment_link.py:88` (`<time>.desc(), <Model>.id.desc()`).
- **Throwaway check** (rowkit, rolled back,
  `bf_dao_attachment_markup_event_test`): three entries forced to one
  `created_at`, one entry a minute later, the lowest of the three updated
  afterwards, plus 260 older entries and one row in another workspace. The
  result had 265 rows (all of them), the head was `later, 8371, 8370, 8369`
  (ties highest id first after the update), the full list was strictly
  descending on `(created_at, id)`, `attachment_id=0` gave `[]`, and the
  foreign workspace gave `[]`. The signature is now
  `(db, *, workspace_id, attachment_id) -> list[AttachmentMarkupEvent]`.
- **SQL/indexes:** sorting happens in SQL. The existing
  `(attachment_id, created_at)` index still serves the filter and first key.
  The extra `id` key only sorts ties within one attachment's history, which
  is small, so it needs no new index.
- **ruff check** on the changed file: all checks passed.

### Nits
- N1: the new docstring is the only method docstring in this file
  (`create_event` has none). It is accurate and explains why, so it is fine
  to keep. Noted only for consistency within the file.

## 3. Questions (unproven)

None.

## 4. What is good

The fix is minimal and exact: one file, two behaviour changes, and nothing
unrelated. The docstring records why there is no cap, which stops someone
from adding one back later.
