# Platform admin — operator and security guide

Makorsha staff (platform operators) use the **same ERP login** as mill users. Extra access is gated by `profiles.is_platform_admin` (migration `115_platform_admin`).

**Current platform operators (production target):**

| Name | Email |
|------|-------|
| Shohan | `shohanc@hotmail.com` |
| Abid | `getabidallabib@gmail.com` |

---

## Production checklist (Railway)

Platform admin is **not** configured on the frontend (Vercel). It lives in **Railway PostgreSQL** behind the API.

| Layer | Host | What you configure |
|-------|------|-------------------|
| Frontend | Vercel | Nothing — reads `is_platform_admin` from API after login |
| Backend + DB | Railway | `profiles.is_platform_admin` column |

### 1. Confirm migration on Railway DB

Every Railway deploy runs `alembic upgrade head` via [`scripts/railway_start.sh`](../scripts/railway_start.sh). After deploy, migration `115_platform_admin` should be applied.

**Verify in Railway Postgres → Query:**

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'profiles' AND column_name = 'is_platform_admin';
```

If the column is missing, run once with production `DATABASE_URL`:

```bash
cd backend
alembic upgrade head
```

### 2. Grant both operators (production)

**Prerequisite:** Each person must have registered and logged in on **production** at least once so a `profiles` row exists.

**Method A — Grant script (recommended)**

From your machine or a Railway one-off shell, with **production** `DATABASE_URL`:

```powershell
cd backend
$env:DATABASE_URL="postgresql://..."   # Railway Postgres connection string
python -m scripts.grant_platform_admin shohanc@hotmail.com getabidallabib@gmail.com
```

**Method B — SQL in Railway Postgres console**

```sql
UPDATE profiles SET is_platform_admin = true
WHERE lower(email) IN ('shohanc@hotmail.com', 'getabidallabib@gmail.com')
RETURNING id, email, is_platform_admin;
```

**Verify:**

```sql
SELECT id, email, is_platform_admin FROM profiles
WHERE lower(email) IN ('shohanc@hotmail.com', 'getabidallabib@gmail.com');
```

Both rows must show `is_platform_admin = true`.

### 3. Refresh sessions

After the DB grant, existing JWTs may still have the old flag.

Each operator should either:

- **Sign out and sign in** on production (`https://frontend-theta-dusky-91.vercel.app/`), or
- Visit `/dashboard` so `AuthProfileSync` runs `GET /auth/me/` and updates Redux.

### 4. Verify in the UI

| Check | Expected |
|-------|----------|
| Sidebar (bottom) | **Platform** link |
| `/platform/support` | Cross-workspace support inbox |
| `/platform/waitlist` | Waitlist signups |
| Mill user (non-admin) | No Platform link; `/platform/*` redirects to dashboard |

---

## Local development bootstrap

Same steps against your local `.env` `DATABASE_URL`:

```bash
cd backend
alembic upgrade head
python -m scripts.grant_platform_admin shohanc@hotmail.com getabidallabib@gmail.com
```

Then sign out/in or open `/dashboard` locally.

---

## What platform admin is

- A boolean on your **profile row** in PostgreSQL — not a separate admin password or frontend env var.
- Checked on every platform API call server-side (`get_platform_admin` in `app/core/deps.py`).
- Checked in the UI by `RequirePlatformAdmin` (reads `user.is_platform_admin` from Redux, synced from `/auth/me/`).

You cannot grant or revoke platform admin from the ERP UI. Only someone with database access (or the grant script against that database) can change the flag.

---

## What you can do

```
Login (production ERP)
  → GET /auth/me/ returns is_platform_admin: true
  → /platform/* routes unlock
       → /platform/support   — all mill help tickets (cross-workspace)
       → /platform/waitlist  — landing page waitlist signups
```

### Support inbox (`/platform/support`)

- List and open help tickets from **all workspaces**.
- Read ticket body, category, creator, mill name.
- Reply via **discussion thread** on the ticket.
- View/upload **attachments** on the ticket.
- **Close / reopen** tickets.

When you select a ticket, the app temporarily sets the API workspace header (`X-Workspace-ID`) to that ticket’s mill so discussions and attachments hit the correct workspace. This uses `setWorkspaceHeaderOnly` — it does **not** wipe the rest of the app cache (avoids inbox flicker).

### Waitlist (`/platform/waitlist`)

- View landing-page waitlist signups.
- Update signup status (e.g. contacted, approved).

Platform admins get waitlist access automatically. Legacy fallback: `WAITLIST_ADMIN_EMAILS` in Railway backend env (comma-separated emails) — not required if `is_platform_admin = true`.

---

## What you cannot do (scope limits)

- **Not a global superuser inside a mill.** Orders, inventory, finance, etc. still follow normal workspace membership and RBAC for your role in that workspace.
- **Cannot impersonate another user’s login** — you act as yourself with the platform flag.
- **Cannot grant admin from the UI** — DB/script only.
- **Platform routes still require authentication** — no anonymous access to `/platform/*` or platform API endpoints.

---

## Security model

| Control | Behavior |
|---------|----------|
| **Authentication** | JWT Bearer token on every API request |
| **Platform authorization** | `profiles.is_platform_admin` checked in `get_platform_admin` |
| **Workspace isolation (normal users)** | Must be a member of the workspace in `X-Workspace-ID` |
| **Workspace isolation (platform admin)** | May use any valid workspace id in `X-Workspace-ID` for support context (e.g. ticket’s mill) — see `get_current_workspace` |
| **Waitlist** | Platform admin **or** legacy `WAITLIST_ADMIN_EMAILS` env allowlist |
| **Revocation** | `UPDATE profiles SET is_platform_admin = false WHERE email = '...'` then user re-login |
| **Secrets** | Never put admin emails in frontend env. Keep `DATABASE_URL`, `SECRET_KEY`, and Railway variables private |

### Protect these assets

- **Railway Postgres** — anyone with write access can grant platform admin.
- **Railway backend env** — `SECRET_KEY` forges JWTs; `DATABASE_URL` exposes all tenant data.
- **Operator accounts** — use strong passwords; platform admin + mill owner role is high privilege.

### What attackers cannot do (by design)

- Call platform list endpoints without a valid JWT **and** `is_platform_admin = true` → **403**.
- Toggle `is_platform_admin` via API — flag is not exposed in user-editable profile PATCH.
- Access platform UI routes without `user.is_platform_admin` in session → redirect to dashboard.

---

## Runbooks

### Grant platform admin

Production: see [Production checklist](#production-checklist-railway) above.

Local:

```bash
python -m scripts.grant_platform_admin email@example.com
```

Multiple emails in one command:

```bash
python -m scripts.grant_platform_admin shohanc@hotmail.com getabidallabib@gmail.com
```

### Revoke platform admin

```sql
UPDATE profiles SET is_platform_admin = false
WHERE lower(email) = lower('email@example.com')
RETURNING id, email, is_platform_admin;
```

User must sign out and back in (or visit `/dashboard` for profile sync).

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| **Platform** link missing | Flag false or stale session | Grant on **same DB as API**; re-login |
| Platform link but inbox **403** | Grant on local DB, API uses Railway | Run grant/SQL on production Postgres |
| Inbox **503** + schema message | Migration `115` not on that DB | `alembic upgrade head` on Railway DB |
| Inbox **500** | Server bug | Check Railway/backend logs |
| Fake **CORS / ERR_FAILED** in Chrome | Often a 500 with no body | Check Network tab status + backend traceback |
| Inbox flicker on ticket click | Old frontend without header-only workspace fix | Deploy latest frontend |

### Optional: legacy waitlist env (Railway)

Not required for platform admins. Only if you want waitlist access **without** `is_platform_admin`:

```
WAITLIST_ADMIN_EMAILS=shohanc@hotmail.com,getabidallabib@gmail.com
```

Set on **Railway backend service → Variables**. Prefer `is_platform_admin` instead.

---

## Deployed URLs

| Service | URL |
|---------|-----|
| Frontend (Vercel) | `https://frontend-theta-dusky-91.vercel.app/` |
| API (Railway) | `https://backend-production-847f.up.railway.app/api/v1/` |
| OpenAPI | `https://backend-production-847f.up.railway.app/api/v1/docs` |

---

## Related docs

- Design spec: [frontend/docs/superpowers/specs/2026-08-20-help-platform-support-design.md](../../frontend/docs/superpowers/specs/2026-08-20-help-platform-support-design.md)
- Upgrade / env notes: [UPGRADING-2026-08-01.md](./UPGRADING-2026-08-01.md)
- Grant script: [scripts/grant_platform_admin.py](../scripts/grant_platform_admin.py)
