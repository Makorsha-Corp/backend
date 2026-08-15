# Manual verification — Cloudinary attachments

Complete these steps after configuring credentials and running migration `104`.

**Hosted (Railway + Vercel):** see [`HOSTED_MOBILE_UPLOAD.md`](HOSTED_MOBILE_UPLOAD.md) first.

## Prerequisites

- [ ] Backend `.env` has valid `CLOUDINARY_*` vars
- [ ] `alembic upgrade head` applied
- [ ] Cloudinary account: PDF/ZIP delivery enabled (Settings → Security)
- [ ] Logged in as workspace **owner**

## Tests at `/uploads`

| Case | Expected |
|------|----------|
| Upload JPEG | Thumbnail appears; confirm returns `ready`; lightbox works |
| Upload PDF | First-page thumb (`pg_1`); download link works |
| Upload >10 MB | Sign rejected with 400 before Cloudinary POST |
| Upload `.zip` | Client validation error (unsupported type) |
| Toggle "Load attachments" off | No list API call; turn on → list loads |
| Delete attachment | Removed from grid; soft-deleted in DB |

## API smoke (optional)

```bash
# After login + workspace header
curl -H "Authorization: Bearer $TOKEN" -H "X-Workspace-ID: 1" \
  "http://localhost:8000/api/v1/attachments/?entity_type=scratch&entity_id=1"
```
