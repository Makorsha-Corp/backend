"""Validate env vars needed for hosted attachments + mobile upload.

Run from backend/ with production .env loaded (or Railway CLI env):

    python -m scripts.verify_hosted_upload_config

Exits 0 when ready; 1 with a checklist of missing/weak settings.
"""
from __future__ import annotations

import sys

from app.core.config import settings


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not settings.CLOUDINARY_CLOUD_NAME:
        errors.append("CLOUDINARY_CLOUD_NAME is empty")
    if not settings.CLOUDINARY_API_KEY:
        errors.append("CLOUDINARY_API_KEY is empty")
    if not settings.CLOUDINARY_API_SECRET:
        errors.append("CLOUDINARY_API_SECRET is empty")

    if settings.ENVIRONMENT == "production" and settings.CLOUDINARY_UPLOAD_ENV != "production":
        warnings.append(
            "ENVIRONMENT=production but CLOUDINARY_UPLOAD_ENV is not 'production' "
            "(uploads will use Dev/ folder prefix)"
        )

    cors = settings.BACKEND_CORS_ORIGINS
    if settings.ENVIRONMENT == "production":
        has_https = any(o.startswith("https://") for o in cors)
        if not has_https:
            errors.append(
                "BACKEND_CORS_ORIGINS has no https:// origin — add your Vercel frontend URL "
                "(phone /m/ page calls the API cross-origin)"
            )

    for msg in warnings:
        print(f"WARN: {msg}")
    for msg in errors:
        print(f"FAIL: {msg}")

    if errors:
        print("\nSee docs/HOSTED_MOBILE_UPLOAD.md for Railway + Vercel setup.")
        return 1

    print("OK: Cloudinary credentials set.")
    if settings.ENVIRONMENT == "production":
        print(f"OK: CORS origins: {', '.join(cors)}")
    print("Next: enable PDF/ZIP delivery in Cloudinary Security; redeploy; run E2E QR test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
