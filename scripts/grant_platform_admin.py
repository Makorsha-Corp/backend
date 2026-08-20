"""One-off: grant is_platform_admin to a profile by email."""
from __future__ import annotations

import sys

from sqlalchemy import text

from app.db.session import SessionLocal


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.grant_platform_admin you@example.com [other@example.com ...]")
        raise SystemExit(1)

    emails = [arg.strip() for arg in sys.argv[1:] if arg.strip()]
    if not emails:
        print("Usage: python -m scripts.grant_platform_admin you@example.com [other@example.com ...]")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        failed: list[str] = []
        for email in emails:
            result = db.execute(
                text(
                    """
                    UPDATE profiles
                    SET is_platform_admin = true
                    WHERE lower(email) = lower(:email)
                    RETURNING id, email, is_platform_admin
                    """
                ),
                {"email": email},
            )
            rows = result.fetchall()
            if not rows:
                failed.append(email)
                continue
            for row in rows:
                print(f"Updated profile id={row[0]} email={row[1]} is_platform_admin={row[2]}")
        if failed:
            db.rollback()
            print(f"No profile found for: {', '.join(failed)}")
            raise SystemExit(1)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
