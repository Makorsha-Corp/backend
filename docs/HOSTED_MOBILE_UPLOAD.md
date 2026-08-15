# Hosted mobile scanner + upload — deployment checklist

Use this after pushing migration `112_merge_heads` (merges the attachment branch with the SO branch). Railway runs migrations automatically via [`scripts/railway_start.sh`](../scripts/railway_start.sh).

**Secrets:** Cloudinary credentials go on **Railway only**. Vercel gets **`VITE_API_URL` only** — never `CLOUDINARY_API_SECRET`.

---

## Fix: "Cloudinary cloud name and API key are required" (hosted only)

Local works, hosted phone upload fails → **Railway backend** missing `CLOUDINARY_*` vars (phone calls Railway `public/sign`, not Vercel).

1. Open local [`backend/.env`](../.env) — copy the three Cloudinary values.
2. **Railway → service that serves `backend-production-847f.up.railway.app` → Variables**
3. Add or update:

| Variable | Value |
|----------|-------|
| `CLOUDINARY_CLOUD_NAME` | from local `.env` |
| `CLOUDINARY_API_KEY` | from local `.env` |
| `CLOUDINARY_API_SECRET` | from local `.env` |
| `CLOUDINARY_UPLOAD_ENV` | `production` |
| `BACKEND_CORS_ORIGINS` | `https://frontend-theta-dusky-91.vercel.app,http://localhost:5173` (adjust Vercel URL if different) |

4. **Redeploy** the backend service (variables load at process start).
5. Retest: desktop **From phone** → scan QR → upload on phone.

CLI alternative (after `railway link` to the **correct** backend service — verify URL contains `backend-production-847f`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_railway_upload_env.ps1
railway redeploy
```

**Do not** add Cloudinary vars to Vercel.

---

## 1. Railway (backend)

### Migrations

1. Ensure `112_merge_heads.py` is on `main` and deployed.
2. Redeploy the backend service (or wait for auto-deploy).
3. Confirm logs show `=== migrations OK ===` (not a multiple-heads error).
4. Expected final stamp: `112_merge_heads`.

If the DB was at `106_completion_codes`, deploy applies `104_attachments_cloudinary` … `111_help_tickets`, then the merge.

### Environment variables

Set in **Railway → backend service → Variables**:

| Variable | Production value |
|----------|------------------|
| `CLOUDINARY_CLOUD_NAME` | Cloudinary dashboard → Settings → Account details |
| `CLOUDINARY_API_KEY` | same |
| `CLOUDINARY_API_SECRET` | same (**server-only secret**) |
| `CLOUDINARY_UPLOAD_ENV` | `production` |
| `ENVIRONMENT` | `production` |
| `BACKEND_CORS_ORIGINS` | Include Vercel frontend origin, e.g. `https://frontend-theta-dusky-91.vercel.app` — comma-separate multiple origins if needed |
| `FRONTEND_BASE_URL` | Same Vercel URL (used for payment redirects) |

Keep existing `DATABASE_URL` and `SECRET_KEY`.

**`CLOUDINARY_UPLOAD_ENV`** is an app folder prefix (`Dev/` vs production paths), not a separate Cloudinary product key. Use one Cloudinary account with `development` locally and `production` on Railway, or separate Cloudinary accounts for stronger isolation.

Validate locally before deploy:

```bash
python -m scripts.verify_hosted_upload_config
```

Sync from local `.env` to linked Railway service (after `railway login` + `railway link`):

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File scripts/sync_railway_upload_env.ps1
```

```bash
# macOS / Linux
bash scripts/sync_railway_upload_env.sh
```

Then redeploy the Railway backend service.

---

## 2. Vercel (frontend)

Set in **Vercel → frontend project → Environment Variables** (Production):

| Variable | Value |
|----------|-------|
| `VITE_API_URL` | `https://backend-production-847f.up.railway.app/api/v1` |

Redeploy after changing env vars (Vite bakes them at build time).

**Do not** add Cloudinary keys to Vercel. The backend sign endpoints return `api_key` + `signature` per upload; only `api_secret` stays on Railway.

Copy from [`frontend/.env.example`](../../frontend/.env.example) for local dev.

---

## 3. Cloudinary dashboard

In the account whose credentials are on Railway:

1. **Settings → Security** — enable **Allow delivery of PDF and ZIP files** (required for PDF attachments).
2. Confirm **authenticated** uploads/delivery work (app uses `type=authenticated`).

See also [`CLOUDINARY_ATTACHMENTS_VERIFY.md`](CLOUDINARY_ATTACHMENTS_VERIFY.md).

---

## 4. End-to-end test (hosted)

1. Log in at the Vercel frontend as a workspace member.
2. Open an order (or `/uploads`) with **AttachmentPanel**.
3. Click **From phone** (QR dialog; desktop width `md+`).
4. Scan QR on phone — URL is `https://<vercel-host>/m/<token>`.
5. Use camera or file picker → CamScan if image → upload completes.
6. Desktop polling shows **uploaded** → enter name → **Attach** (promote).
7. Attachment appears with thumbnail.

### Failure modes

| Symptom | Likely cause |
|---------|----------------|
| Deploy loop / migration error | Multiple Alembic heads — ensure `112_merge_heads` is deployed |
| 503 on QR create | `CLOUDINARY_*` missing on Railway |
| Phone “invalid or expired” | Expired token, bad QR, or migration `109` not applied |
| Phone fails at sign/confirm | CORS — add Vercel origin to `BACKEND_CORS_ORIGINS` |
| Cloudinary POST fails | Wrong credentials or Cloudinary security settings |
| Desktop never sees upload | JWT / polling — check network tab on desktop |

---

## Architecture (why secrets split this way)

```
Desktop (Vercel)  --JWT-->  Railway sign/session
Phone (Vercel)    --token--> Railway public/sign/confirm
Phone             --file-->  Cloudinary direct upload
Desktop           --JWT-->  Railway promote (Admin API rename)
```

Phone page: [`MobileUploadPage`](../../frontend/src/pages/newpages/MobileUploadPage.tsx) at `/m/:token`. Security notes: [`ATTACHMENT_UPLOAD_SECURITY.md`](ATTACHMENT_UPLOAD_SECURITY.md).
