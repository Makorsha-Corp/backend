"""Profile stamp image upload — Cloudinary direct upload for saved stamps."""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.cloudinary_client import (
    AUTHENTICATED_DELIVERY_TYPE,
    CloudinaryNotConfiguredError,
    destroy_resource,
    generate_upload_signature,
)
from app.core.config import settings
from app.models.profile import Profile
from app.schemas.saved_stamp import SavedStampImage, StampImageSignResponse


class ProfileStampManager:
    """Mint signed upload params and cleanup for profile stamp images."""

    def _upload_env(self) -> str:
        return settings.CLOUDINARY_UPLOAD_ENV or settings.ENVIRONMENT

    def build_stamp_public_id(self, *, user_id: int) -> str:
        token = uuid.uuid4().hex
        base = f"profiles/{user_id}/stamp-{token}"
        if self._upload_env() == "production":
            return base
        return f"{self._upload_env()}/{base}"

    def build_stamp_asset_folder(self, *, user_name: str, user_id: int) -> str:
        safe_name = user_name.replace("/", "-").replace("\\", "-").strip() or f"user-{user_id}"
        folder = f"Profile stamps/{safe_name}"
        if self._upload_env() == "production":
            return folder
        return f"Dev/{folder}"

    def sign_stamp_image_upload(self, user: Profile) -> StampImageSignResponse:
        if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
            raise CloudinaryNotConfiguredError("Cloudinary cloud name and API key are required.")

        public_id = self.build_stamp_public_id(user_id=user.id)
        asset_folder = self.build_stamp_asset_folder(user_name=user.name, user_id=user.id)
        display_name = "saved-stamp"
        timestamp = int(time.time())
        signature = generate_upload_signature(
            public_id=public_id,
            asset_folder=asset_folder,
            display_name=display_name,
            timestamp=timestamp,
            delivery_type=AUTHENTICATED_DELIVERY_TYPE,
        )
        cloud_name = settings.CLOUDINARY_CLOUD_NAME
        upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

        return StampImageSignResponse(
            cloud_name=cloud_name,
            api_key=settings.CLOUDINARY_API_KEY,
            timestamp=timestamp,
            public_id=public_id,
            asset_folder=asset_folder,
            display_name=display_name,
            type=AUTHENTICATED_DELIVERY_TYPE,
            signature=signature,
            resource_type="image",
            upload_url=upload_url,
        )

    def destroy_saved_stamp_image(self, saved_stamp: dict[str, Any] | None) -> None:
        if not saved_stamp or saved_stamp.get("kind") != "image":
            return
        public_id = saved_stamp.get("public_id")
        if not public_id:
            return
        try:
            destroy_resource(public_id=public_id, resource_type="image")
        except Exception:
            pass

    def validate_saved_stamp_payload(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if payload is None:
            return None
        kind = payload.get("kind")
        if kind == "vector":
            from app.schemas.saved_stamp import SavedStampVector

            return SavedStampVector.model_validate(payload).model_dump()
        if kind == "image":
            return SavedStampImage.model_validate(payload).model_dump()
        raise ValueError("saved_stamp.kind must be 'vector' or 'image'.")


profile_stamp_manager = ProfileStampManager()
