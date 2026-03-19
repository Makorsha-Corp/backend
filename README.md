# ERP Backend API

FastAPI backend for the ERP system. By default it runs against a local SQLite database and exposes a versioned REST API under `/api/v1`.

---

## Getting Started (First Time Setup)

### 1. Prerequisites

- **Python**: 3.10 or higher
- **pip**: Python package manager
- (Optional) **Git** if you’re cloning from a repository

### 2. Create and Activate Virtual Environment

From the **backend repo root** (where `requirements.txt` and `app/` live):

```bash
python -m venv .venv
```

Activate it:

- **Windows (PowerShell / CMD):**

```bash
.venv\Scripts\activate
```

- **Linux / macOS:**

```bash
source .venv/bin/activate
```

You should now see `(.venv)` in your shell prompt.

### 3. Install Dependencies

With the virtual environment active:

```bash
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic, and the other required packages.

### 4. Environment Configuration

By default, the app uses SQLite and built‑in defaults from `app/core/config.py`:

- `DATABASE_URL = "sqlite:///./erp.db"`
- `ENVIRONMENT = "development"`
- `DEBUG = True`

If you have an `.env` file, it will be loaded automatically and can override these values. For local development you can usually run without any extra configuration.

---

## Running the Application

From the `backend` directory with the virtualenv active:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

This will:

- Create / migrate the SQLite database file `erp.db` in the project root (via `Base.metadata.create_all`).
- Run any lightweight startup initialization in `app/main.py`.
- Start the API at: `http://localhost:8000`

You should see logs in the terminal showing Uvicorn starting and requests being handled.

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

- **Default DB**: SQLite file `erp.db` in the backend root.
- Tables are created automatically on startup via SQLAlchemy models in `app/models` and `app/db/base.py`.
- When a workspace is created, default workspace‑scoped data (statuses, departments, tags, account tags) is seeded by the workspace service.

### Alembic Migrations (Optional)

For more controlled schema management:

- **Create migration**:

```bash
alembic revision --autogenerate -m "description"
```

- **Apply migrations**:

```bash
alembic upgrade head
```

- **Rollback**:

```bash
alembic downgrade -1
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
