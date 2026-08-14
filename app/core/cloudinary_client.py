"""Cloudinary SDK wrapper — single integration point for storage operations."""
from __future__ import annotations

from typing import Any

import cloudinary
import cloudinary.api
import cloudinary.uploader
import cloudinary.utils

from app.core.config import settings


class CloudinaryNotConfiguredError(RuntimeError):
    """Raised when Cloudinary env vars are missing."""


def _ensure_configured() -> None:
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        raise CloudinaryNotConfiguredError(
            "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET."
        )
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


AUTHENTICATED_DELIVERY_TYPE = "authenticated"


def generate_upload_signature(
    *,
    public_id: str,
    asset_folder: str,
    display_name: str,
    timestamp: int,
    delivery_type: str = AUTHENTICATED_DELIVERY_TYPE,
) -> str:
    """Generate SHA signature for signed direct browser upload (dynamic folder mode)."""
    _ensure_configured()
    params_to_sign = {
        "timestamp": timestamp,
        "public_id": public_id,
        "asset_folder": asset_folder,
        "display_name": display_name,
        "type": delivery_type,
    }
    return cloudinary.utils.api_sign_request(params_to_sign, settings.CLOUDINARY_API_SECRET)


def build_signed_delivery_url(
    *,
    public_id: str,
    resource_type: str,
    delivery_type: str,
    version: int,
    fmt: str,
    transformation: list[dict[str, Any]] | None = None,
    flags: str | None = None,
) -> str:
    """Build a signed delivery URL (authenticated or legacy upload type)."""
    _ensure_configured()
    options: dict[str, Any] = {
        "resource_type": resource_type,
        "type": delivery_type,
        "sign_url": delivery_type == AUTHENTICATED_DELIVERY_TYPE,
        "format": fmt,
        "version": version,
        "secure": True,
    }
    if transformation:
        options["transformation"] = transformation
    if flags:
        options["flags"] = flags
    url, _options = cloudinary.utils.cloudinary_url(public_id, **options)
    return url


def get_resource(
    *,
    public_id: str,
    resource_type: str = "image",
    delivery_type: str = AUTHENTICATED_DELIVERY_TYPE,
) -> dict[str, Any]:
    """Fetch asset metadata from Cloudinary Admin API."""
    _ensure_configured()
    return cloudinary.api.resource(
        public_id,
        resource_type=resource_type,
        type=delivery_type,
    )


def destroy_resource(
    *,
    public_id: str,
    resource_type: str = "image",
    delivery_type: str = AUTHENTICATED_DELIVERY_TYPE,
) -> dict[str, Any]:
    """Remove asset from Cloudinary."""
    _ensure_configured()
    return cloudinary.uploader.destroy(
        public_id,
        resource_type=resource_type,
        type=delivery_type,
        invalidate=True,
    )


def rename_resource(
    *,
    from_public_id: str,
    to_public_id: str,
    resource_type: str = "image",
    delivery_type: str = AUTHENTICATED_DELIVERY_TYPE,
) -> dict[str, Any]:
    """Move an asset to a new public_id. Admin JSON only — no file bytes."""
    _ensure_configured()
    return cloudinary.uploader.rename(
        from_public_id,
        to_public_id,
        resource_type=resource_type,
        type=delivery_type,
        to_type=delivery_type,
        invalidate=True,
    )


def update_resource_metadata(
    *,
    public_id: str,
    resource_type: str = "image",
    delivery_type: str = AUTHENTICATED_DELIVERY_TYPE,
    asset_folder: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Update Media Library folder / display name. Admin JSON only."""
    _ensure_configured()
    options: dict[str, Any] = {
        "resource_type": resource_type,
        "type": delivery_type,
    }
    if asset_folder is not None:
        options["asset_folder"] = asset_folder
    if display_name is not None:
        options["display_name"] = display_name
    return cloudinary.api.update(public_id, **options)
