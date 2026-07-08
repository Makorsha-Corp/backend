"""
Database initialization and seeding

Global seed data (subscription plans) is created here at app startup.
Workspace-scoped seed data (statuses, departments, tags) is
created when a workspace is created - see:
- seed_default_statuses() in app/db/seed_default_statuses.py
- seed_default_departments() in app/db/seed_default_departments.py
- seed_default_tags() in app/db/seed_default_tags.py
- seed_default_account_tags() in app/db/seed_default_account_tags.py

Work order types are NOT seeded by default - each workspace starts with an
empty list and users define their own vocabulary via the Maintenance wizard.
"""
from sqlalchemy.orm import Session
from app.db.seed_default_subscription_plans import seed_default_subscription_plans


def init_db(db: Session) -> None:
    """
    Initialize database with global default data.

    Called once at app startup. Seeds subscription plans which must
    exist before any user can register/create a workspace.

    Schema is managed exclusively by Alembic — run `alembic upgrade head`
    before starting the server locally or on Railway.

    Args:
        db: Database session
    """
    seed_default_subscription_plans(db)
    db.commit()
