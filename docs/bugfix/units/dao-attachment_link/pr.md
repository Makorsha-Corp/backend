## fix(attachment_link): BUG-1432, BUG-1433, BUG-1434

Branch: `bugfix/dao-attachment_link` → `main` (commit `11db000`). Risk: `normal`. The owner merges.

### Bugs

| Id | Title | Intended |
|---|---|---|
| BUG-1432 | Attachments with one upload time come back in no fixed order | HR-6: `uploaded_at` newest first, then `id` descending, before `skip` / `limit` |
| BUG-1433 | The links of one attachment have no order | HR-6: `id` ascending |
| BUG-1434 | A failed upload keeps using up one of the record's 25 attachment places | `failed` attachments are not counted; `pending` ones still are |

### The change

All in `app/dao/attachment_link.py` (4 lines):

- `get_attachments_for_entity` sorts by `uploaded_at DESC, id DESC` before paging, so attachments with the same upload time keep a fixed order and pages don't repeat or skip rows.
- `get_links_for_attachment` sorts by `attachment_links.id ASC`, so `links[0]` is the first link made. The attachment ledger uses it as the record when no record is named.
- `count_linked_attachments_for_entity` leaves out `upload_status = 'failed'`. Pending uploads still hold their place, and deleted ones still never count. The docstring is updated to match.

The PR also removes the 12 xfail markers for these bugs (DAO, attachment manager and attachment service tests) and marks the three bugs Fixed in `docs/testing/bugs.md`.

### Impact (systems engineer, round 1: APPROVE)

- Callers: `AttachmentService.list_attachments` (`GET /attachments/`), `AttachmentManager.assert_entity_attachment_capacity` (`POST /attachments/sign`, phone promote), `_append_attachment_ledger`, `_log_attachment_entity_events` and `to_response`. None of them relied on the old order. The capacity refusal is the same, but it now comes only once 25 attachments are pending or ready.
- Retrying a failed upload can now take a record past 25. That's accepted under the soft-cap decision (manager spec Q15) and needs a direct API call.
- Failed rows will pile up once BUG-2095 / BUG-2204 are fixed. That costs storage, not correctness, and the clean-up sweep (FU-3) should cover them.
- No database change, no migration, no lock or transaction effect.

### Contract note

No shape, status-code or message change. One value changes meaning: `slot_count` in `GET /attachments/` now counts pending and ready attachments only. Example: a purchase order with 20 ready photos and 5 failed uploads used to return `slot_count: 25` (the panel showed "25/25" and blocked uploads). Now it returns `20`. The order of `items` and `links` is now fixed. `AttachmentPanel.tsx` already handles this, so there is **no frontend PR**.

### Flip check

Base `d5fea1c` (`docs/bugfix/baseline-d5fea1c.json`), full suite, 4 workers: **CLEAN**. 12 tests flipped xfail → passed as intended, 0 other changes (`docs/bugfix/units/dao-attachment_link/flipcheck.json`). Alembic still has one head (`124_help_ticket_status`), and no migration was added.

Note: the worktree has no `.env`. The first run failed two legacy tests (`tests/test_attachments.py::test_derive_urls_*`) with `CloudinaryNotConfiguredError`. That's caused by the environment, not the fix. The final run used placeholder `CLOUDINARY_*` values.

### Data-check script

None needed.
