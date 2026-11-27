# Contract note: dao-attachment_link (round 1, 2026-11-27)

No contract change (no shape, status code or message changes). One value now means something different, and the frontend already handles it correctly:

- **`GET /attachments/?entity_type=..&entity_id=..` → `slot_count`** now counts `pending` + `ready` attachments only. Failed uploads are left out (BUG-1434). `max_per_entity` (25) is unchanged. Example: a purchase order with 20 ready photos and 5 failed uploads used to return `slot_count: 25`, so the panel showed "25/25 attachments — delete one to add more" and blocked uploads. Now it returns `slot_count: 20` and uploads stay open.
- **`POST /attachments/sign`** and **`POST /mobile-upload/sessions/{id}/promote`** refuse with the same 400 `"This record already has the maximum of 25 attachments."`, but only once 25 attachments are pending or ready. Failed ones no longer count.
- **Order only:** `items` of `GET /attachments/` is newest first and then highest `id` when upload times tie (BUG-1432). `links` in every attachment response is in link-creation order (BUG-1433).

Frontend: `AttachmentPanel.tsx` already reads `slot_count` / `max_per_entity` and sorts `items` itself. No change needed, so the frontend stage is skipped.
