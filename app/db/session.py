"""
Database session configuration
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _set_postgres_session_utc(dbapi_connection, _connection_record) -> None:
    """App stores naive datetimes and serializes them as UTC.

    Postgres `now()` follows the session TimeZone. A Dhaka session writes wall
    clock, then the API labels that value Z, so activity shows about 6 hours ahead.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET TIME ZONE 'UTC'")
    finally:
        cursor.close()


if settings.DATABASE_URL.startswith("postgres"):
    event.listen(engine, "connect", _set_postgres_session_utc)
