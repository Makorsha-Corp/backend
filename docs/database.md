# Database and migrations

Schema is managed by **Alembic**. The FastAPI app does not run `create_all` at startup.

## Local development

```bash
docker-compose -f docker/docker-compose.yml up -d
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify schema after upgrading:

```bash
python scripts/verify_db.py
```

Reset local data and re-apply migrations:

```bash
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up -d
alembic upgrade head
python scripts/verify_db.py
```

## Railway deployment

Railway runs [`scripts/railway_start.sh`](../scripts/railway_start.sh), which:

1. Runs `alembic upgrade head` (fails the deploy if migrations fail)
2. Starts uvicorn

Set `DATABASE_URL` in Railway to your hosted Postgres instance. Pull changes locally, run migrations, confirm, then push — Railway applies the same migration chain on deploy.

## Adding a new table or column

1. Create or update the SQLAlchemy model in `app/models/`.
2. Import the model in [`app/db/base.py`](../app/db/base.py) so Alembic autogenerate sees it.
3. Export from [`app/models/__init__.py`](../app/models/__init__.py) if the model is part of the public package.
4. Generate a migration:

   ```bash
   alembic revision --autogenerate -m "short description"
   ```

5. Make the migration **idempotent** when `001` may already create the object on fresh installs — use helpers from [`app/db/migration_helpers.py`](../app/db/migration_helpers.py):

   - `table_exists`, `column_exists`
   - `add_column_if_not_exists`, `drop_column_if_exists`
   - `create_unique_constraint_if_not_exists`, `drop_unique_constraint_if_exists`

6. Run locally:

   ```bash
   alembic upgrade head
   python scripts/verify_db.py
   ```

7. Commit the migration and deploy to Railway.

## Migration chain notes

- **`001`** runs `Base.metadata.create_all()` from current models. Fresh databases get the latest model snapshot at revision 001; later revisions apply incremental deltas (mostly no-ops on fresh installs when idempotent).
- **Never rely on re-running 001** to update an existing database — always add an incremental migration for schema changes.
- Revisions **`019`–`021`** are empty placeholders kept for deploy compatibility; do not delete them.
- **`alembic.ini`** `sqlalchemy.url` is a placeholder; runtime URL comes from `DATABASE_URL` in `.env` via `alembic/env.py`.

## Startup seeding

[`app/db/init_db.py`](../app/db/init_db.py) seeds **global** subscription plans only. Workspace-scoped defaults (statuses, departments, tags) are created when a workspace is created.
