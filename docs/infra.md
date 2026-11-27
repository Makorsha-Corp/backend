# Infrastructure plan (backend)

> Status: **SUGGESTIONS, for discussion** (started 2026-11-21). Nothing in this file is built yet. Goes with `docs/ci-cd.md`, which covers how code gets tested and deployed.

## 1. Where we are today

| Piece | Today | Notes |
|---|---|---|
| Backend | **One** Railway service running `uvicorn` via `Procfile` → `scripts/railway_start.sh` | That script also migrates on every start (`alembic upgrade head`). |
| Database | **One** Railway Postgres instance | This is production; there is no second copy. |
| Frontend / landing page | Vercel (per `.env.example`) | Separate repos `../frontend` and `../landingPage`. |
| File storage | Cloudinary (`CLOUDINARY_*`, with `CLOUDINARY_UPLOAD_ENV` to separate folders) | |
| Payments | SSLCommerz (`SSLCOMMERZ_*`); mock mode and sandbox flags exist | The subscription portal comes later. |
| Bot protection | Cloudflare Turnstile (`TURNSTILE_SECRET_KEY`) on the waitlist | |
| Local | `docker/docker-compose.yml` (Postgres 16) + `uvicorn` on the dev machine; tests use `marker_test` | |
| Background jobs / Redis | None | `docs/realtime-architecture.md` plans SSE later; Redis only if there are ever several backend workers. |

**The risk today:** every change is tried directly against production, on production data. There is nowhere to try a migration, a payment-flow change or a Railway setting first.

## 2. Target: three environments

> **Updated 2026-11-21:** there are now four environments: local, dev, **staging** and prod. Staging holds a real-data copy of prod and is reachable only by the owner (see the §9 decisions log). The table below shows the original three. Staging has prod's settings, except that payments are in sandbox mode, outgoing messages are off, and it has its own secrets.

| | **Local** | **Development (dev)** | **Production (prod)** |
|---|---|---|---|
| Who uses it | one developer | the team, for testing and demos | customers |
| Where | dev machine | Railway project, environment `development` | Railway project, environment `production` |
| Backend | `uvicorn --reload` | 1 Railway service | 1 Railway service (scale later) |
| Database | Docker Postgres `marker_db` + `marker_test` (tests) | its **own** Railway Postgres | its own Railway Postgres, **backups on** |
| Data | seed / fake data | seed data, never a raw copy of production | real customer data |
| Deploys from | your working copy | `main`, automatically, once CI is green | a **promotion** of what is already running on dev (§4) |
| Frontend | `localhost:5173` | a Vercel *preview/dev* deployment pointed at the dev API | Vercel production |
| SSLCommerz | `SSLCOMMERZ_MOCK_MODE=true` | sandbox store (`SSLCOMMERZ_SANDBOX=true`, sandbox credentials) | live store |
| Cloudinary | `CLOUDINARY_UPLOAD_ENV=development` | `development` (or `dev`) | `production` |
| `DEBUG` | true | false | false |
| `WORK_ORDER_ALLOW_DEV_DELETE` | allowed | allowed only if needed for testing | **always false** |

### Why Railway *environments* rather than a second Railway project
- **Same project, separate environments.** One Railway project holds `production` and `development`. Each gets its **own copy of every service** (backend + Postgres) with its **own variables**. Nothing is shared between them unless you link it on purpose.
- **Easy to create.** A new environment can be duplicated from production's setup in one click: same services and settings, an empty database and new variables.
- **PR environments later.** Railway can spin up a short-lived environment for each PR, for reviewing a change before it merges. Optional (§7).

## 3. What each environment needs (variables)

From `app/core/config.py`. Set these **per environment** in Railway; never share secrets across environments.

| Variable | Local | Dev | Prod | Notes |
|---|---|---|---|---|
| `DATABASE_URL` | local Docker | dev Postgres (Railway reference variable) | prod Postgres (reference variable) | Use Railway's `${{Postgres.DATABASE_URL}}` reference so it is never typed by hand. |
| `SECRET_KEY` | any | **unique** | **unique, long, random** | Different per environment, so a dev token never works on prod. |
| `ENVIRONMENT` | `development` | `development` (or a new `staging` value) | `production` | Check what code branches on this value before adding a new one. |
| `DEBUG` | `true` | `false` | `false` | |
| `BACKEND_CORS_ORIGINS` | localhost ports | dev frontend URL(s) | prod frontend + landing URLs | |
| `FRONTEND_BASE_URL` / `BACKEND_BASE_URL` | localhost | dev URLs | prod URLs | SSLCommerz callbacks use these, so a wrong value sends payments to the wrong place. |
| `SSLCOMMERZ_MOCK_MODE` / `_SANDBOX` / `_STORE_ID` / `_STORE_PASSWORD` | mock | sandbox credentials | live credentials | Live credentials exist **only** in prod. |
| `CLOUDINARY_*` | dev keys (or same account, dev folder) | same, `UPLOAD_ENV=development` | `UPLOAD_ENV=production` | Ideally a separate Cloudinary account or key for prod. |
| `TURNSTILE_SECRET_KEY` | test key | test key | real key | Cloudflare provides always-pass test keys. |
| `WAITLIST_ADMIN_EMAILS`, `WAITLIST_IP_HASH_SALT` | any | own salt | own salt | |
| `WORK_ORDER_ALLOW_DEV_DELETE` | `true` if wanted | `false` by default | **`false`** | Deletes without returning stock. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `MAX_ATTACHMENTS_PER_ENTITY` | defaults | defaults | defaults | |

**Suggestion:** a short `docs/env-vars.md`, or a table in `.env.example`, listing every variable, who owns it and where it is set. That way adding an environment is a checklist, not guesswork.

## 4. How code moves: local → dev → prod

Two options. Pick one.

**Option A, branch per environment (simplest).**
- `main` → **dev** automatically (Railway "Wait for CI" on).
- A `production` branch → **prod**. Releasing is a fast-forward merge (or PR) from `main` into `production`.
- *Good:* uses only Railway's built-in GitHub deploys; easy to understand.
- *Catch:* Railway builds the app separately for each environment, so prod runs a fresh build of the same commit, not the exact thing tested on dev. In practice that is very rarely a problem with locked dependencies (see `ci-cd.md`, the lock file).

**Option B, build once, promote the same image.**
- CI builds a Docker image per commit and pushes it to GitHub's registry. Dev runs it.
- Releasing to prod points the prod service at **that same image tag**.
- *Good:* prod runs byte-for-byte what was tested on dev.
- *Catch:* needs a Dockerfile, a registry and a small release workflow.

**Suggestion:** start with **A**, and move to **B** if you adopt the build-once suggestion in `ci-cd.md`.

**Release checklist (either option):**
1. The change has been on dev and was checked there, including any migration.
2. CI is green on the commit.
3. Prod backup is recent (Railway backups, see §5).
4. Promote. Then open the app and check the changed area.

## 5. Database

### Separation
- **Dev and prod have separate Postgres instances.** Dev is never pointed at prod data, and prod is never used for experiments.
- Never copy production data into dev as it is: it holds customer names, phone numbers, emails and payment records. If realistic data is needed, use a seed script, or a copy with personal fields scrubbed (a later task).

### Migrations
- **Move migrations out of the start script** into Railway's **pre-deploy command**, in both environments. They then run once per deploy, before the new version starts. If one fails, the deploy stops and the old version keeps running.
- Every migration runs on **dev first**, through the normal flow, before prod sees it.
- Schema changes that would break the running version go in two steps (add the new column first, remove the old one later), as described in `ci-cd.md`.

### Backups
- **Prod:** turn on Railway Postgres backups, and check how often they run and how long they are kept on your plan. **Practise a restore once**, into a scratch database, and write down the steps.
- **Dev:** backups optional; it can be reset from seed data.

### Local
- Keep `docker/docker-compose.yml` for Postgres. Suggestions:
  - a second database for tests is already handled by the test setup (`marker_test`, plus one per worker later);
  - a `scripts/seed_dev.py` that creates a demo workspace, accounts, items and a few orders. That makes local and dev useful straight away, and it is the same script used to fill dev after a reset.

## 6. Local development

What a new developer should be able to do in about 10 minutes:

```
docker compose -f docker/docker-compose.yml up -d     # Postgres
cp .env.example .env                                   # local values
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_dev                             # (to be written)
uvicorn app.main:app --reload
pytest tests/unit -o addopts=""                         # runs on marker_test
```

**Suggestions:**
- **A short `README` section** with exactly these steps.
- **`.env.example` kept complete,** with every variable and a safe local default. Local must never need a real secret: SSLCommerz in mock mode, Turnstile test keys, and Cloudinary dev keys or uploads turned off.
- **Optionally run the backend in Docker too,** so local matches Railway more closely. This isn't needed while there's one developer.

## 6a. Building with AI agents

AI agents need **throwaway sandboxes**, not more permanent environments. Dev and prod stay as planned, and agents reach them only through a PR.

```
Agent sandbox (per task, throwaway) → PR → CI → (PR preview env) → human review → main → dev → prod (human)
```

### Sandboxes, one per agent task
- **What each one gets:**
  - its own git worktree or branch;
  - its own Postgres (Docker, or one database per task, the same pattern as one database per test worker);
  - SSLCommerz in mock mode, Turnstile test keys, and Cloudinary off or a dev folder;
  - **no real secrets**.
- **Where they run:** locally (worktrees + per-task databases), or in cloud sandboxes (Claude Code remote/cloud sessions, or containers), which also isolates the dev machine.
- **Lifetime:** created at task start and deleted at the end, data included.

### PR preview environments
- **A temporary environment per PR.** Railway PR environments give each PR its own temporary backend and database, so an agent's change can be tried out before merging. They are torn down when the PR closes. Moved forward from §7, because this is the main infrastructure addition that helps agentic work.

### Guardrails
- **No credentials for agents.** Agents never hold prod or dev credentials: no database URL, no live payment keys, no Railway deploy token.
- **Everything through a PR.** Branch protection on `main` applies to agents too.
- **CI is the gate.** The ~21k unit tests encode every rule agreed in the test sweep. A strict-xfail XPASS flags a fixed bug.
- **CODEOWNERS on risky paths.** Money, payments, stock, migrations and permissions always need the owner's review.
- **Migration checks.** Migration linting and the round-trip test (`ci-cd.md`) catch table-locking or irreversible migrations.
- **Limits.** Each agent task has a cost/time budget, and there is a cap on concurrent agents.
- **Traceable.** Every change is a commit or PR with its reasoning in the description.

### Autonomy levels
| Level | Agents may | When |
|---|---|---|
| 1 | Open PRs; a human merges | Start |
| 2 | Auto-merge low-risk PRs (tests, docs, non-money code) once CI is green; risky paths still need the owner | When CI is trusted |
| 3 | Also deploy to dev automatically | Later |

Production promotion stays a human decision at every level.

## 7. Later (not needed now)
- **PR environments** on Railway: each PR gets a temporary backend and database, and is torn down on merge.
- **More than one backend instance** in prod:
  - needs migrations in pre-deploy first (§5);
  - Redis pub/sub if the SSE plan in `realtime-architecture.md` is built.
- **A scrubbed copy of prod data for dev:** a script that copies prod and replaces names, phones and emails.
- **A custom domain per environment,** for example `api.<domain>` for prod and `api-dev.<domain>` for dev.
- **Cost check:** a second environment roughly doubles the Railway bill for the backend and database. Dev can run on smaller resources, and can sleep when idle if the plan allows.

## 8. Open questions for the owner
1. **Frontend:** is the frontend on Vercel? Should dev have its own Vercel deployment pointed at the dev API?
2. **Release flow:** option A (a `production` branch) or option B (promote the same image)?
3. **Who may deploy to prod:** only you, or anyone who can merge?
4. **SSLCommerz:** do you already have sandbox credentials separate from the live store?
5. **Cloudinary:** is a separate account or key for prod OK, or the same account with different folders?
6. **Domains:** do you have a domain for the API, or are you using Railway's generated URLs?
7. **Railway plan:** which plan are you on (for backups and for the cost of a second environment)?
8. **Agent sandboxes:** where should agents run? Locally (worktrees plus a database per task), in cloud sandboxes, or both?
9. **Autonomy level to start at:** level 1 (a human merges everything) is suggested. Which areas count as "risky paths" for CODEOWNERS?

## 9. Decisions log
- **2026-11-21: release flow agreed in principle by the owner.**
  1. An agent (or a person) works on a branch.
  2. **Preview deployment per branch/PR**, which the owner clicks through and tests:
     - frontend on a Vercel preview URL;
     - backend on a Railway PR environment with its own throwaway database;
     - the frontend preview is wired to its matching backend preview.
  3. The owner gives the green light, and the PR is merged into `main`.
  4. CI runs the full suite on `main`. It also runs on the PR before review.
  5. `main` deploys to **dev** automatically. Dev uses seed or fake data.
  6. The release is promoted to **staging**, which holds a fresh copy of the real production database, and is tested there on real data.
  7. The owner releases to **prod**.
- **2026-11-21: a staging environment with real data (owner wants testing on real data).**
  - **Staging is temporary, one per release (owner, 2026-11-21).**
    1. Create it, or bring back its kept setup (services and variables).
    2. Restore the latest prod backup into it.
    3. Deploy the release there and test it.
    4. **Delete the staging database afterwards.**

    Real customer data exists outside prod only for the length of a release test. A short script or checklist (`docs/runbooks/staging.md`, to write) covers these steps, so the delete step is never skipped.
  - **Access is the same as prod:** only the owner holds its database URL and Railway access. Agents never get its credentials, and it never appears in agent tasks.
  - **Real data never goes into dev, previews or agent sandboxes.** Those use seed data. A scrubbed copy of prod can be added to dev later if realistic data is wanted there.
  - **Staging must not reach real people or money:**
    - SSLCommerz in sandbox/mock mode;
    - all outgoing email, SMS or notifications off or redirected. That matters most once the notifications feature exists;
    - its own Cloudinary folder (`CLOUDINARY_UPLOAD_ENV=staging`);
    - its own `SECRET_KEY`;
    - `WORK_ORDER_ALLOW_DEV_DELETE=false`.
