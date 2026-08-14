# Cloudinary Attachment Uploads — Design Spec

**Date:** 2026-08-10  
**Status:** Approved for implementation

## Summary

Signed direct browser upload to Cloudinary with public delivery. FastAPI mints signatures and owns metadata; browser sends bytes to Cloudinary; confirm step verifies against Cloudinary Admin API. Polymorphic `attachment_links` table links files to any entity. `/uploads` playground page exercises the pipeline.

## Decisions

| Topic | Choice |
|-------|--------|
| Upload path | Signed direct (browser → Cloudinary); `CLOUDINARY_API_SECRET` server-side only |
| Delivery | Public `type=upload`, unguessable random `public_id` tail |
| Linking | Polymorphic `attachment_links` table |
| Folder | `makorsha/{env}/ws-{workspace_id}/{entity_type}/{entity_id}/{uuid4hex}` |
| Files | Images (jpg/png/webp/heic) + PDF; PDF preview via `pg_1` |
| Confirm | Verified against Cloudinary Admin API |
| Test page | Standalone `/uploads` playground; reusable `AttachmentPanel` |

## URL derivation

Persist `public_id`, `version`, `format`, `resource_type`. Derive URLs at read time:

- **thumb:** `f_auto,q_auto,w_400,c_limit/v{version}/{public_id}.{format}`
- **full:** `f_auto,q_auto/v{version}/{public_id}.{format}`
- **pdf page:** `pg_1,f_jpg,q_auto,w_400,c_limit/v{version}/{public_id}.jpg`
- **download:** `fl_attachment/v{version}/{public_id}.{format}`

## Entity types

`purchase_order`, `sales_order`, `expense_order`, `transfer_order`, `work_order`, `project`, `project_component`, `item`, `machine`, `account_invoice`, `scratch`

## Upload flow

1. `POST /attachments/sign` — validate mime/size, mint `public_id`, insert `pending` row + link, return signature params
2. Browser `POST` multipart to `https://api.cloudinary.com/v1_1/{cloud}/image/upload`
3. `POST /attachments/{id}/confirm` — Admin API `resource(public_id)`, update row to `ready`
4. `GET /attachments/?entity_type=&entity_id=` — list with derived URLs (lazy from client)
5. `DELETE /attachments/{id}` — soft delete + Cloudinary destroy

## Schema

**attachments** (extended): `storage_provider`, `public_id`, `resource_type`, `delivery_type`, `format`, `version`, `width`, `height`, `asset_id`, `etag`, `upload_status` (`pending` \| `ready` \| `failed`); `file_url` nullable audit copy.

**attachment_links:** `id`, `workspace_id`, `attachment_id`, `entity_type`, `entity_id`, `linked_at`, `linked_by`; unique on `(attachment_id, entity_type, entity_id)`; index on `(workspace_id, entity_type, entity_id)`.

## Manual prerequisite

Enable **Allow delivery of PDF and ZIP files** in Cloudinary Settings → Security.

## Future

Moving to private `type=authenticated` delivery requires config change + signed URL endpoint, not a schema rewrite (we store `public_id`, not rendered URLs).
