# Impact review: dao-attachment_link, round 1 (2026-11-27)

Diff: `git -C E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-attachment_link diff origin/main -- app alembic`.
Four lines in `app/dao/attachment_link.py` (three clauses and a docstring); nothing in `alembic/`. The worktree has no other changes.

- `get_attachments_for_entity`: `ORDER BY uploaded_at DESC` becomes `uploaded_at DESC, id DESC`, still before `OFFSET` / `LIMIT` (BUG-1432, R6).
- `count_linked_attachments_for_entity`: adds `upload_status != 'failed'` (BUG-1434, R1). Docstring updated.
- `get_links_for_attachment`: adds `ORDER BY attachment_links.id ASC` (BUG-1433, R4).

I compiled all three queries to Postgres SQL from the worktree. They give `ORDER BY attachments.uploaded_at DESC, attachments.id DESC LIMIT .. OFFSET ..`, `... AND attachments.upload_status != 'failed'` and `ORDER BY attachment_links.id ASC`. These are ORM column sorts, so the SQL has `.id` in it. The tester pre-check's strict SQL-text checks need exactly that.

## Upstream

| Changed method | Caller | Effect |
|---|---|---|
| `get_attachments_for_entity` | `AttachmentService.list_attachments` (`app/services/attachment_service.py:112`) ← `GET /attachments/` | Attachments that share one `uploaded_at` now come back in a fixed order, and pages don't repeat or skip rows. The service passes the list through. The frontend's `AttachmentPanel` re-sorts it (`sortedAttachments`). Nothing relied on the old, undefined tie order. |
| `count_linked_attachments_for_entity` | `AttachmentManager.assert_entity_attachment_capacity` (`app/managers/attachment_manager.py:102`) ← `create_pending_attachment` ← `AttachmentService.sign_upload` (`POST /attachments/sign`) and `MobileUploadSessionManager.promote_to_attachment` (`:478`, `POST /mobile-upload/sessions/{id}/promote`) | Failed uploads no longer count toward the 25. A record with failed uploads can take new uploads until 25 are pending or ready. The refusal (`AttachmentLimitError` → 400, the same message on both endpoints) is unchanged. It just comes later. |
| `count_linked_attachments_for_entity` | `AttachmentService.list_attachments` (`:120`) → `slot_count` | The value drops by the number of failed, non-deleted uploads. The shape is unchanged. See "Frontend-visible effect". |
| `get_links_for_attachment` | `AttachmentManager._append_attachment_ledger` (`:251`) | `links[0]` is now the first link made, so every ledger write that names no entity (ready, failed, deleted) uses the record the attachment was first attached to. That is the intended effect (link DAO FU-1 (c)). |
| `get_links_for_attachment` | `_log_attachment_entity_events` (`:311`) | It loops over every link. Only the order of the activity writes changes, and each goes to its own record. |
| `get_links_for_attachment` | `to_response` (`:649`) → every attachment response (`links`) | `links` comes back in link-id order. The shape is unchanged. |

No other module calls these three methods (checked `app/` for each name). The attachment ledger (`ledger_manager.get_attachment_ledger`, `GET /ledgers/attachments`) reads `attachment_ledger` only. It never counts attachments or links, so BUG-1434 doesn't reach it. Return types, `[]` vs `0`, raised errors and keyword-only signatures are unchanged.

### BUG-1434 in detail

- **Pending still counts and deleted never counts.** `upload_status` is `String(16) NOT NULL` with default `pending` (`app/models/attachment.py:48`), so `!=` can't drop a row through NULL logic. The only values ever written are `UploadStatusEnum` values (`pending`, `ready`, `failed`; `app/models/enums.py:163`). The column has no CHECK constraint, so an unknown value would count, which is the safe direction.
- **List and count agree better now.** The list shows `ready` only and the count is `pending + ready`. The gap that remains is uploads in flight, which the spec says hold their place (Q1).
- **Retrying a failed upload can push a record over 25 (non-blocking, decided).** `confirm_attachment` accepts a `failed` attachment again and can make it `ready`. That retry is intended (manager spec R8, BUG-2093) and runs no capacity check. With failed uploads no longer counted, this can happen: a record has 25 ready photos and one failed scan, and confirming the scan again gives 26 ready. Before this fix the failed scan held its place, so that path couldn't pass 25. I treat this as intended under the manager spec Q15 decision: the limit is "a soft cap against clutter", and two parallel signs at 24 already reach 26. It is not money, stock, order workflow or security, so there is no question for the owner. The browser never re-confirms a failed upload (`AttachmentPanel` confirms right after signing), so only a direct API call can do this. Decided by Claude under the reviewer's delegation (2026-11-27). No bug.
- **Real-world reach today is small.** BUG-2095 (web confirm) and BUG-2204 (phone promote) roll back the `failed` state, so a failed confirm leaves the attachment `pending`, and pending still counts. Until those two are fixed, `failed` rows are rare (written only by a path that commits after the failure, which no service does today). This fix is still right and needed: once BUG-2095 / BUG-2204 land, failed rows will persist, and without this fix each one would take a place for good.

### Failed rows piling up (note, no question)

After BUG-2095 / BUG-2204, failed uploads will build up. They are invisible in the list, no longer counted, and each one usually still has a Cloudinary file (BUG-2099 deletes it only on an explicit delete, and the user can't see the row to delete it). That costs storage, not correctness: no code assumes "at most 25 rows per record". The fixer's risk note checks out, and I found the same. The clean-up job is already proposed in the attachment manager spec FU-3 (sweep old `pending` rows, delete the files). It should cover old `failed` rows too. FU-3 says it is "noted in `docs/future/subscription-payments.md` (storage)", but that file has no attachment or Cloudinary entry. **For the orchestrator:** add a line there (failed and stale pending attachments keep Cloudinary files, so a sweep is needed before storage quotas matter). It is not a bug and not a question.

### `"failed"` string vs `UploadStatusEnum`

The literal is acceptable. The same query family already filters with the literal `"ready"` two methods up, and the DAO imports no enum. `UploadStatusEnum` is a `str` enum whose `.value` is exactly `"failed"`, so behaviour is identical. Switching only the new filter to `UploadStatusEnum.FAILED.value` would leave the file half-literal. Switching both would touch an unrelated line, which is out of scope. Not blocking. A later tidy could move both filters to `UploadStatusEnum.<X>.value` to match the managers.

## Downstream

Plain `SELECT` / `COUNT` with an extra filter or sort key. No locks, flushes or commits. `id` is the primary key on both tables, and `upload_status` is indexed. The capacity check stays unlocked (Q15, intended). No transaction-contract (TC1–TC6) effect.

## API contract

The shape doesn't change. One value changes: `slot_count` in `GET /attachments/` no longer includes failed uploads, and `POST /attachments/sign` / the phone promote refuse at 25 pending + ready instead of 25 including failed. Recorded in `contract.md`.

**Frontend-visible effect:** `AttachmentPanel.tsx:191-193,351` shows `"{slot_count}/{max_per_entity} attachments — delete one to add more"` and disables uploads when `slot_count >= max_per_entity`. With failed uploads in the count, a user could see "25/25" next to fewer files, with nothing visible to delete. After the fix the hint and the lock match what they can see, apart from uploads in flight. The frontend logic is already correct for the new value, so no frontend change is needed.

## Database

No migration, constraint or index. No check script needed.

## Neighbouring bugs

- **BUG-2095, BUG-2204** (failed state rolled back): they limit how much this fix shows today (above). No clash. Fixing them later makes this fix matter.
- **BUG-2093** (retry after failed writes no "Attached"): the over-25 retry path above. No clash.
- **BUG-2099** (pending / failed files left in Cloudinary on delete): related to clean-up only. No clash.
- **BUG-1870** (private records' attachments visible): this DAO compares the link's workspace only, as before. Not reached.
- **BUG-1431** (`linked_at` local time, model file): untouched. Links are now ordered by `id`, not `linked_at`, so they don't interact.
- **BUG-2133** (phone promote checks capacity after the Cloudinary move): same capacity check, with a lower count. No clash.
- `get_by_entity` still has no `ORDER BY`. The brief puts it out of scope (no caller, listed for removal), and the fixer correctly left it alone.

## Shortcuts / scope

None. Each change is the rule as written: HR-6 keeps the chosen order and adds `id` last in the stated direction, and BUG-1434 drops only `failed`. The docstring change matches the new behaviour. Nothing outside the three bugs changed. It matches the tester pre-check: an ORM `id` sort, so `.id` is in the SQL, and pending is still counted.

## Risk tag

Stays `normal`. BUG-1434's pattern is not on the trivial list, and it changes a user-visible value (`slot_count`) and when the limit refuses. It is not `owner-area` (not money, stock, order workflow or security) and not `db-change`.

## Verdict

**APPROVE.** To the tester.
