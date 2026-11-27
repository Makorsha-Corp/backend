# CI/CD plan (backend)

> Status: **SUGGESTIONS ONLY** (started 2026-11-21). The owner is rethinking the plan, so nothing here is agreed or built yet, apart from what "Where we are today" describes. Tags such as [core] and [later] below are Claude's suggestions, not decisions.

## 1. Basics

- **CI (continuous integration):** on every push and every pull request, a fresh machine installs the app, lints it, runs the tests and checks the migrations. A red result means "don't merge".
- **CD (continuous delivery/deployment):** once code lands on `main` and CI is green, it goes to the server automatically.
- **Where it runs:** GitHub Actions, configured by YAML files in `.github/workflows/`.
  - A *workflow* is made of *jobs*. Jobs run in parallel, each on its own fresh Linux machine.
  - A job is a list of *steps*.
  - A job can start *service containers*, for example Postgres, that live only as long as the job does.

## 2. Where we are today

| Piece | What exists | Notes |
|---|---|---|
| `.github/workflows/ci.yml` → `test` job | `pip install -r requirements.txt`, then `pytest -q` | **No Postgres.** It works for the 48 older tests in `tests/*.py`, which mostly don't need a database. It **will break** once `tests/unit/` is pushed, because those tests need a real Postgres. |
| `.github/workflows/ci.yml` → `migrations` job | Postgres 16 service; checks there is exactly one Alembic head; `alembic upgrade head` on an empty database | Good. Keep it. |
| Deploy | Railway: `Procfile` → `scripts/railway_start.sh`, which adopts the squashed baseline, runs `alembic upgrade head`, then starts uvicorn | Probably auto-deploys on every push to `main`, **without waiting for CI** (to confirm, §7). |
| Lint | `ruff` is used locally | Not in `requirements.txt` and not run in CI. |
| Local database | `docker/docker-compose.yml` (Postgres 16) | — |

### The test suite as of 2026-11-21

- **Size:**
  - `tests/unit/`: ~20,300 tests across ~200 files. There will be ~21,000 when the sweep is finished.
  - 48 older tests in `tests/*.py`.
- **Run time:** about **16 minutes** serial on the dev machine (943 s).
  - Setup: ~300 s. Most of it builds test data in the database.
  - Test bodies: ~160 s.
  - The rest is collection, start-up and many tiny tests.
  - Slowest files: `test_auth_service.py` (27 s, password hashing), then the machine item, work order template and machine managers (~19 s each).
- **Result shape:** about 15,200 passed, about 5,000 expected to fail (`xfail`), 70 expected to fail that passed anyway (`xpassed`), 1 skipped.
  - The `xfail` tests are known bugs, each with an ID in `docs/testing/bugs.md`. They are expected and keep the build green.
  - The `xpassed` tests are by design. ~400 tests depend on physical row order and are marked *non-strict*; each is paired with a strict check of the SQL itself.
  - **Strict** `xfail` tests that start passing *fail the build*. That is the signal that someone fixed the bug, and the marker must now be removed.
- **Database contract** (`tests/unit/conftest.py`):
  - `TEST_DATABASE_URL` must point at a database whose name ends in `_test`, or the run refuses to start.
  - The database is created if missing and migrated to head once per session.
  - Every test runs inside a transaction that is rolled back, so tests never see each other's rows.
- **Warnings:** 816 per run, almost all from the app's deprecated `HTTP_422_UNPROCESSABLE_ENTITY`. They are harmless, but worth clearing so that real warnings stand out.

## 3. Goals

1. A PR can't be merged unless lint, tests and migrations pass.
2. CI results come back in **≤ 10 minutes**, ideally ~5.
3. Production only receives commits that passed CI on `main`.
4. Known bugs never block work, but a *fixed* bug can't go unnoticed (strict xfail).
5. Cheap to run: GitHub's free minutes for a private repo are 2,000 per month (to confirm for the org's plan).

## 4. Proposed layout

### 4.1 Workflow files

```
.github/
  workflows/
    ci.yml          # on: pull_request, push to main
    nightly.yml     # on: schedule (later, phase 5)
requirements.txt        # app runtime (unchanged)
requirements-dev.txt    # new: -r requirements.txt + ruff, pytest-xdist
```

### 4.2 Jobs in `ci.yml`

```
            ┌──────────┐
 push / PR ─┤  lint    │  ruff check  (~30 s)
            ├──────────┤
            │migrations│  one head + upgrade on empty DB  (existing, ~1 min)
            ├──────────┤
            │ legacy   │  pytest tests/*.py  (no DB, existing tests)
            ├──────────┤
            │ unit (×N)│  Postgres service + pytest tests/unit, split N ways
            └──────────┘
                 │ all green
                 ▼
         merge allowed (branch protection)
                 │ push to main, CI green
                 ▼
         Railway deploys ("Wait for CI")
```

All four jobs run in parallel. The PR is green only when every one of them is green.

### 4.3 The unit-test job: how to make 16 minutes into ~5

**Option A: one job, `pytest-xdist -n 4`.** One runner, 4 worker processes.
- *Good:* the simplest setup, and it uses the runner's 4 cores.
- *Catch:* all workers would share one `marker_test` database. Rollback isolation makes that mostly safe, but a few tests lock whole tables or rows (workflow locks, advisory checks) and may wait on each other. The clean fix is **one database per worker**: a small change in `conftest.py` turns `marker_test` into `marker_test_gw0`, `marker_test_gw1`, and so on, using xdist's `worker_id`. This is test code only, not app code.
- *Expected:* about 5–6 minutes.

**Option B: a matrix of 3–4 jobs, split by folder** (`dao`, `managers`, `services` + `core`/`utils`/`integrations`).
- *Good:* every job has its own runner and its own Postgres, so there is no shared-database question. A failure shows which layer broke.
- *Catch:* uneven split (managers is the biggest), each job pays its own install and migrate (~1 min), and it uses more CI minutes.
- *Expected:* about 6–7 minutes, at the speed of the slowest job.

**Option C: A + B together** (a matrix where each job uses xdist). Not worth it at today's size.

**Recommendation:** **Option A** with one database per worker. If the run time grows later, move to sharding with `pytest-split` and timing data.

### 4.4 Sketch of the unit-test job (not final)

```yaml
unit:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env: { POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres, POSTGRES_DB: postgres }
      ports: ["5432:5432"]
      options: >-
        --health-cmd "pg_isready -U postgres" --health-interval 5s
        --health-timeout 5s --health-retries 10
  env:
    TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/marker_test
    DATABASE_URL: postgresql://postgres:postgres@localhost:5432/marker_test
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.12', cache: pip }
    - run: pip install -r requirements-dev.txt
    - run: python -m pytest tests/unit -n 4 -q -o addopts="" -p no:cacheprovider
```

Note that `pytest.ini` sets `addopts = -v`. That prints 21,000 lines into the CI log, so CI overrides it.

### 4.5 Branch protection (GitHub → Settings → Branches → `main`)

- Require a pull request before merging.
- Require these status checks to pass: `lint`, `migrations`, `legacy`, `unit`.
- Require branches to be up to date before merging (optional; it costs extra runs).
- Do not allow bypassing (owner included?), to be decided in §7.

### 4.6 CD on Railway

- **Minimum:** in the Railway service settings, turn on **"Wait for CI"**. Railway then deploys a `main` commit only after the GitHub checks pass. No deploy script is needed, because `railway_start.sh` already runs the migrations.
- **Later:** a **staging** environment, with its own Railway environment and its own database, deployed from a `develop` branch or from each PR (Railway "PR environments"). Changes are tried there before `main`.
- **Railway features to use:**
  - **Wait for CI:** deploy a `main` commit only after its GitHub checks pass.
  - **Pre-deploy command for migrations:**
    - Move `alembic upgrade head` (and the baseline-adoption step) out of `railway_start.sh` into Railway's pre-deploy command.
    - It then runs exactly once per deploy, before the new version starts. If it fails, the deploy stops and the old version keeps serving.
    - Today every app instance migrates at start, which races once there is more than one replica.
  - **Healthcheck path** (e.g. `/health`): traffic switches only when the new version answers, which gives zero-downtime deploys.
  - **Environments:** `staging` with its own database and variables, deployed from `develop`, or PR environments.
  - **Postgres backups:** confirm they are on and that a restore has been practised.
- **Don't** run the test suite on Railway (as a build step, for example). It slows every deploy by ~16 minutes, costs compute, and there is no throwaway database per run. CI stays on GitHub Actions.
- **Migrations safety:**
  - CI's `migrations` job proves the chain applies to an empty database.
  - It does not prove the chain applies to production's *current* state.
  - A staging database restored from a recent production snapshot would cover that (phase 5).

## 5. Phases

| Phase | What | Effort | Blocks on |
|---|---|---|---|
| 1 | Add `requirements-dev.txt`; `lint` job; Postgres for unit tests; keep the legacy tests in their own job | small | §7 Q1 |
| 2 | `pytest-xdist`, one database per worker (conftest change), `-n 4` | small | — |
| 3 | Branch protection on `main` | settings only | §7 Q3 |
| 4 | Railway "Wait for CI" | settings only | §7 Q2 |
| 5 | Nightly workflow: full suite + `tests/unit/_tools/mutate.py` on changed modules; coverage report on PRs; Dependabot; staging environment | medium | after launch? |

**Before turning CI on for `tests/unit/`:** finish the sweep, or at least make sure every committed test file is green (passes or expected failures only). Also decide when the test files get committed (they are untracked today).

## 6. Things to clean up first (optional, but they make CI nicer)

- The 816 deprecation warnings (`HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT`). This change is in `app/`, so it waits until the testing phase allows app edits.
- `pytest.ini`'s `addopts = -v` is too noisy for CI. Change it to `-q`, or override it in CI.
- Pin `ruff` to a version so local runs and CI agree.
- Merge the two duplicate bug-pattern slugs in `bugs.md` (`exclude-none-blocks-clear` / `exclude-none-blocks-clearing`). This is cosmetic.

## 6a. Production-grade target (what strong production teams do)

The goal is a pipeline you'd recognise at a well-run product company, sized for a small team. Each item is tagged:
- **[core]** do it;
- **[later]** after launch;
- **[skip]** overkill at our size, listed so the choice is deliberate.

### Principles
1. **Trunk-based development** [core]. Short-lived branches, small PRs, `main` always deployable. No long-lived `develop` branch; staging deploys from `main`.
2. **Build once, promote the same artifact** [core]. CI builds **one Docker image** per commit, tagged with the commit SHA and pushed to GitHub Container Registry (GHCR). Staging and production both run *that exact image*. Railway never rebuilds from source for production. This removes "it worked in staging but production built differently".
3. **Fast feedback** [core]. PR checks finish in ≤ 10 min. Slow checks (mutation, full integration) run nightly or before release, never on every push.
4. **Everything as code** [core]. Workflows, Dockerfile and environment settings live in the repo. Railway settings are written down in this doc (Railway config-as-code `railway.json` where possible).
5. **Least privilege** [core]. Each workflow gets a minimal `GITHUB_TOKEN`: `permissions: contents: read` by default, widened per job. Deploy credentials live only in the protected `production` environment.
6. **Reversible by default** [core]. Every deploy can be rolled back in one click (Railway redeploys the previous image). Every migration is written so the *previous* app version still works against the new schema (expand/contract, below).

### Pipeline stages

```
PR opened / updated
  ├─ lint & format         ruff check, ruff format --check
  ├─ types (gradual)       pyright on new/changed modules        [later]
  ├─ security              pip-audit, gitleaks, CodeQL           (see Supply chain)
  ├─ migrations            one head · alembic check (models ⇄ migrations) ·
  │                        upgrade on empty DB · downgrade -1 then upgrade
  │                        again · migration lint (squawk)
  ├─ unit tests            xdist ×4, one DB per worker; JUnit report; coverage
  │                        on changed lines posted to the PR
  ├─ legacy tests          tests/*.py
  ├─ build image           docker build (cache), Trivy scan, no push on PRs
  └─ API contract          export OpenAPI, diff vs main, flag breaking changes
        │ all green + 1 approving review
        ▼
Merge queue → main        re-runs the required checks on the merged result  [later]
        ▼
main pipeline
  ├─ same checks
  ├─ build + push image    ghcr.io/makorsha-corp/backend:<sha>, SBOM + provenance
  ├─ deploy → staging      Railway staging runs the image; pre-deploy runs migrations
  ├─ smoke tests (staging) /api/v1/health + read-only API checks
  └─ deploy → production   GitHub `production` environment: required reviewer
                            (manual approve) or automatic after staging is green
        ▼
post-deploy
  ├─ smoke tests (prod)
  └─ (no error-tracking or paging step: see Observability, which the owner does not want for now)
  └─ release notes from commit messages (release-please)
```

### Supply chain and security
- **Locked dependencies with hashes** [core].
  - Today `requirements.txt` pins only the top-level packages, so transitive versions can change between builds.
  - Move to **uv** (`pyproject.toml` + `uv.lock`), or `pip-compile --generate-hashes`.
  - CI installs only from the lock file; the build fails if the lock is stale.
- **Pin GitHub Actions to commit SHAs** [core]. Use `actions/checkout@<sha>`, not `@v4`, so a compromised tag can't run in our pipeline. Dependabot keeps the SHAs updated.
- **Dependabot** [core] for pip, GitHub Actions and the Docker base image, with weekly grouped PRs.
- **pip-audit** [core] fails on known-vulnerable packages, with a documented ignore list and an expiry date for each entry.
- **Secret scanning + push protection** [core] (GitHub setting), plus **gitleaks** in CI for history.
- **CodeQL** [core] (free for GitHub code scanning on Python): catches injection and unsafe patterns.
- **Container image scan** [core]: Trivy on the built image; fail on critical vulnerabilities that have a fix.
- **SBOM + build provenance** [later] (`docker/build-push-action` with `sbom: true, provenance: true`, or `actions/attest-build-provenance`).
- **Signed images** (cosign) [skip for now]: valuable once several services and teams pull images.

### Database and migrations (the riskiest part of any deploy)
- **`alembic check`** [core] fails when the models and migrations disagree.
- **Round-trip test** [core]: `upgrade head` → `downgrade -1` → `upgrade head`, which proves the newest migration's downgrade works.
- **Migration linting** [core]: run **squawk** on the generated SQL (`alembic upgrade --sql`). It flags patterns that lock big tables:
  - adding a NOT NULL column without a default;
  - creating an index without `CONCURRENTLY`;
  - changing a column type.
- **Timeouts inside migrations** [core]: `SET lock_timeout = '5s'; SET statement_timeout = '60s'`, so a migration waiting on a lock fails fast instead of freezing production.
- **Expand/contract** [core, a team rule]: a breaking schema change ships in two deploys.
  1. Add the new column or table, and let the code write both.
  2. Remove the old one only after every running version stops using it.

  This keeps rollbacks safe.
- **Migrations run once, before the new version starts** [core]: in Railway's pre-deploy command, not in `railway_start.sh`.
- **Rehearse on real data** [later]: a nightly job restores the latest production backup into a scratch database and runs pending migrations against it.
- **Backups and restore drills** [core]: Railway Postgres backups on; a restore actually practised and written down (how long it takes, who does it).

### Testing layers
| Layer | When | Notes |
|---|---|---|
| Unit (`tests/unit`, ~21k) | every PR | Strict xfail = known bugs; an XPASS fails the build so fixed bugs get unmarked. |
| Legacy (`tests/*.py`) | every PR | Fold into `tests/unit` over time. |
| Integration [later] | nightly + before release | Real concurrency (two sessions), the deferred race and lock tests, endpoint-to-database flows. |
| Contract [core] | every PR | OpenAPI diff; frontend CI type-checks against the exported schema. |
| Smoke [core] | after every deploy | Health check plus 3–5 read-only calls; fails → alert + rollback. |
| Mutation | nightly, on changed modules | `tests/unit/_tools/mutate.py`; report the score per module. |
| Load [later] | before big launches | k6 or Locust against staging for the hot endpoints. |

### Environments and promotion
- **Preview per PR** [later]: Railway PR environments with a throwaway database for manual QA.
- **Staging** [core]: same image, same migrations, its own database and secrets. It mirrors production settings, plus non-production SSLCommerz sandbox credentials.
- **Production** [core]: a GitHub `production` environment with protection rules.
  - A required reviewer, or "deploy only after staging smoke passes".
  - Deploys only from `main`.
- **Config and secrets** [core]: per-environment variables in Railway; nothing secret in the repo or the image. `app/core/config.py` reads everything from the environment.
- **Feature flags** [later]: ship code turned off, then switch it on per workspace. This fits the coming permissions and subscription-portal work. A simple database-backed flag table is enough; a vendor isn't needed.
- **Canary / blue-green** [skip]: Railway's healthcheck-gated switch-over already gives zero-downtime deploys at our traffic.

### Observability and operations

> **Owner, 2026-11-21: not wanted for now.** No error tracking, logging dashboards or paging/on-call alerts. The items below stay only as a record of what was considered. They are not part of the roadmap.

- **Error tracking** [core]: Sentry (or similar) with the release set to the commit SHA, so every error links to the deploy that caused it.
- **Structured logs** [later]: JSON logs with request id and workspace id (never personal data).
- **Uptime monitor** [core] on `/api/v1/health`, alerting to email or phone.
- **SLOs** [later]: for example 99.5% of requests succeed and p95 < 500 ms. Alerts fire on the error budget, not on every blip.
- **Runbooks** [core]: one short page each for "deploy failed", "roll back", "restore the database" and "migration stuck".
- **DORA metrics** [later]: deploy frequency, lead time, change failure rate, time to restore. GitHub plus Railway data is enough.

### Repository governance
- **Branch protection / rulesets on `main`** [core]:
  - PR required, with 1 approving review.
  - All required checks green.
  - Linear history (squash merge).
  - No force push.
  - Admins included; an emergency bypass is logged.
- **CODEOWNERS** [core]: `app/managers`, `app/services`, `alembic/` and the payment code need a named reviewer.
- **PR template** [core]: what changed, how it was tested, migration yes/no, rollback plan.
- **Conventional commits** [core, already used] → release-please for versions and changelog.
- **Merge queue** [later]: worth it once several people merge every day.

### Roadmap (replaces §5 once agreed)
| Step | Contents | Size |
|---|---|---|
| A | Lock file (uv), `requirements-dev`, lint job, Postgres unit job with xdist and one DB per worker, legacy job, `concurrency` cancel, action SHAs pinned, minimal `permissions` | 1–2 days |
| B | Migration hardening: `alembic check`, round-trip, squawk, lock timeouts; move migrations to Railway pre-deploy | 1 day |
| C | Security: pip-audit, gitleaks, CodeQL, secret scanning + push protection, Dependabot | half a day |
| D | Dockerfile; build + Trivy on PRs; push to GHCR on `main`; Railway deploys the image; staging environment; smoke tests; `production` environment gate | 2–3 days |
| E | Governance: rulesets, CODEOWNERS, PR template, release-please | half a day |
| F | *(dropped: the owner does not want observability/paging for now)*. Runbooks for rollback and database restore can still live in this doc | — |
| G [later] | Nightly integration + mutation, OpenAPI contract with the frontend, PR previews, feature flags, SLOs, restore-rehearsal job, merge queue | ongoing |

## 7. Open questions for the owner

1. **Legacy tests:** the 48 tests in `tests/*.py`. Keep them as their own job, or move them under `tests/unit/` later? (Most don't need a database; 3 mention an engine or sessions.)
2. **Railway:**
   - Does production deploy straight from `main` today?
   - Is there a staging environment?
   - Are you OK turning on "Wait for CI"?
3. **Branch protection:** are you OK with no direct pushes to `main` for anyone, you included? Or should admins be allowed to bypass?
4. **CI minutes:**
   - Which GitHub plan is the `Makorsha-Corp` org on? Free private repos get 2,000 minutes per month.
   - At ~6 minutes × 4 parallel jobs per push, that is ~25 runner-minutes per push, or roughly 80 pushes a month.
   - Option: run the full unit suite only on PRs and `main`, not on every branch push.
6. **Production deploy gate:** should a human approve each production deploy, or should it go automatically once staging smoke tests pass?
7. **Image-based deploys:** OK to add a Dockerfile and have Railway deploy CI-built images (GHCR) instead of building from source?
8. **Reviewers:** who else reviews PRs? With a single developer, "1 approving review" needs a second person or a documented self-review rule.
9. ~~**Error tracking**~~: not wanted for now (owner, 2026-11-21).
10. **When to switch on:**
   - Right after the test sweep finishes?
   - Or now, with only the finished modules included (the rest added as they pass)?

## 8. Decisions log

- **2026-11-21: the whole document is suggestions only; the owner is rethinking it.**
- **2026-11-21: no error tracking, logging dashboards or paging for now (owner).**
- **2026-11-21: one test database per xdist worker (owner agreed).**
  - As built (2026-11-23): each worker gets `marker_gwN_test` (the `_test` suffix stays last, so the safety check still applies) and migrates it itself. A fresh migration takes about 5 s, so no template clone is needed.
  - A plain run without xdist still uses `marker_test`.
  - `UNIT_TESTS_SKIP_MIGRATE=1` (used by `mutate.py`) keeps working: no migrate, no clone.
  - The worker databases are reused between runs.
  - Drawbacks: a small conftest change, and a few empty databases on dev machines.
- **2026-11-23: CI test jobs built (`.github/workflows/ci.yml`).** Jobs `legacy` (tests/*.py, no DB, dummy Cloudinary env), `unit` (Postgres 16, `pytest tests/unit -n 4`), and `migrations` (unchanged). No `lint` job yet: `ruff check .` has about 1,450 existing findings in `app/`, so it would start red. Add it once those are cleaned up. Three stale legacy attachment tests were updated to current behaviour (attachment limit check mocked; `density: 200` for wide PDF pages, per attachment_manager spec R7).
