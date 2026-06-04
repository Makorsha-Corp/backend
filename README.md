# ERP Backend API

FastAPI backend for the ERP system. By default it runs against a local SQLite database and exposes a versioned REST API under `/api/v1`.

**Pagination:** each list endpoint sets its own `limit` maximum (`le=` in FastAPI). Those caps are easy to outgrow; see the full-stack note at `frontend/docs/api-pagination-limits.md` (in the Marker-Corp workspace) and grep `le=` under `app/api/v1/endpoints/` when changing limits.

---

## Getting Started (First Time Setup)

### Prerequisites

- **Python** 3.10 or higher
- **Docker** (for the local Postgres database)

### 1. Start the database

```bash
docker-compose -f docker/docker-compose.yml up -d
```

This starts a Postgres 16 container on `localhost:5432` with the credentials already in `.env.example`. Data is persisted in a Docker volume so it survives restarts.

To stop it later: `docker-compose -f docker/docker-compose.yml down`  
To wipe all data and start fresh: `docker-compose -f docker/docker-compose.yml down -v`

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

- **Windows (PowerShell):** `.venv\Scripts\activate`
- **macOS / Linux:** `source .venv/bin/activate`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

The defaults in `.env.example` already match the Docker Postgres container, so no edits are needed for local dev.

### 5. Run database migrations

```bash
alembic upgrade head
```

This creates all tables. Re-run this command any time a new migration is added.

### 6. Start the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server starts at `http://localhost:8000`. On startup it automatically seeds global reference data (subscription plans).

---

## Running the Application

From the `backend` directory with the virtualenv active:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

---

## API Documentation

Once the server is running, open these in your browser:

- **Swagger UI (interactive docs)**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`
- **OpenAPI JSON**: `http://localhost:8000/api/v1/openapi.json`

If Swagger UI shows a blank page, make sure the server is running and check the browser console and server logs for errors.

---

## First‑Time Usage Flow

### 1. Register a User

Use Swagger UI (`/api/v1/docs`) or a REST client to call:

- **Endpoint**: `POST /api/v1/auth/register`
- **Body example**:

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "password123",
  "permission": "owner",
  "position": "Manager"
}
```

This creates your first user account.

### 2. Login and Get JWT

Call:

- **Endpoint**: `POST /api/v1/auth/login`
- **Body example**:

```json
{
  "email": "john@example.com",
  "password": "password123"
}
```

The response contains an **access token**. For all authenticated requests, include:

```http
Authorization: Bearer <access_token>
```

### 3. Workspaces and Multi‑Tenancy

The API is designed for **workspace‑based multi‑tenancy**:

- Many endpoints expect a header specifying the current workspace:

```http
X-Workspace-ID: <workspace_id>
```

- The dependency `get_current_workspace` validates that the authenticated user has access to that workspace.
- Workspace‑scoped DAOs and services always filter by `workspace_id`.

Typical flow after login:

1. Create or select a workspace (see the workspace endpoints in Swagger).
2. Use its `id` as `X-Workspace-ID` for all workspace‑scoped endpoints (orders, items, sales, projects, etc.).

---

## Database Notes

- **Local DB**: PostgreSQL 16 running in Docker (`docker-compose up -d`).
- **Schema**: managed by Alembic migrations — always run `alembic upgrade head` after pulling new changes.
- When a workspace is created, default workspace‑scoped data (statuses, departments, tags, account tags) is seeded automatically.

### Alembic Migrations

- **Apply all pending migrations**:

```bash
alembic upgrade head
```

- **Create a new migration** (after changing a model):

```bash
alembic revision --autogenerate -m "description"
```

- **Rollback one step**:

```bash
alembic downgrade -1
```

- **Reset local DB** (wipe everything and re-apply from scratch):

```bash
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up -d
alembic upgrade head
```

---

## Project Structure (Backend)

```text
backend/
├── alembic/              # Database migrations
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/        # Versioned API endpoints
│   │       └── router.py         # Route configuration
│   ├── core/                     # Core configuration & middleware
│   │   ├── config.py             # Settings (pydantic BaseSettings)
│   │   ├── security.py           # Auth helpers (JWT, hashing)
│   │   ├── deps.py               # FastAPI dependencies (DB, user, workspace)
│   │   └── middleware.py         # Request ID, security headers
│   ├── db/                       # Database bootstrap & seeders
│   │   ├── base.py               # Model import glue for Alembic
│   │   ├── base_class.py         # SQLAlchemy base class
│   │   ├── session.py            # Engine & SessionLocal
│   │   ├── init_db.py            # Legacy/global init hook
│   │   ├── seed_default_tags.py
│   │   ├── seed_default_account_tags.py
│   │   ├── seed_default_statuses.py
│   │   └── seed_default_departments.py
│   ├── dao/                      # Data access objects (no commit)
│   ├── managers/                 # Domain managers / orchestration
│   ├── services/                 # Service layer (transactions, messages)
│   ├── models/                   # SQLAlchemy models
│   ├── schemas/                  # Pydantic schemas
│   └── main.py                   # FastAPI app entry point
├── tests/                        # Tests
├── alembic.ini                   # Alembic configuration
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## Testing

With the virtualenv active:

```bash
pytest
```

With coverage:

```bash
pytest --cov=app tests/
```

---

## Development Helpers

- **Format code (Black)**:

```bash
black app/
```

- **Lint (flake8)**:

```bash
flake8 app/
```

- **Type check (mypy)**:

```bash
mypy app/
```

---

## Production Notes (High‑Level)

For production:

- Use **PostgreSQL** (update `DATABASE_URL` in `.env`).
- Set `ENVIRONMENT=production` and `DEBUG=false`.
- Use a strong, secret `SECRET_KEY`.
- Put a proper reverse proxy (Nginx, etc.) and TLS in front.
- Run with a production ASGI server:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## License

Proprietary – Akbar Cotton Mill
