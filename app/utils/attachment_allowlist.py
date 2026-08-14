"""Attachment extension/MIME allowlist — validated at sign/confirm; no file bytes on server.

Authoritative backend source. Frontend mirror: frontend/src/lib/attachmentAllowlist.ts
Docs: backend/docs/ATTACHMENT_UPLOAD_SECURITY.md
When changing types/limits, update both files + tests/test_attachment_allowlist_sync.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, FrozenSet

from app.schemas.attachment import AttachmentSignRequest

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

_FILENAME_UNSAFE = re.compile(r'[\x00-\x1f\x7f<>:"|?*]')


class AttachmentValidationError(ValueError):
    """Invalid upload request."""


class AttachmentConfirmError(ValueError):
    """Confirm step failed (Cloudinary mismatch or missing asset)."""


@dataclass(frozen=True)
class AttachmentTypeSpec:
    extensions: FrozenSet[str]
    mime_types: FrozenSet[str]
    resource_type: str
    confirm_formats: FrozenSet[str]


ATTACHMENT_TYPE_SPECS: tuple[AttachmentTypeSpec, ...] = (
    AttachmentTypeSpec(
        frozenset({"jpg", "jpeg"}),
        frozenset({"image/jpeg"}),
        "image",
        frozenset({"jpg", "jpeg"}),
    ),
    AttachmentTypeSpec(
        frozenset({"png"}),
        frozenset({"image/png"}),
        "image",
        frozenset({"png"}),
    ),
    AttachmentTypeSpec(
        frozenset({"webp"}),
        frozenset({"image/webp"}),
        "image",
        frozenset({"webp"}),
    ),
    AttachmentTypeSpec(
        frozenset({"heic"}),
        frozenset({"image/heic"}),
        "image",
        frozenset({"heic"}),
    ),
    AttachmentTypeSpec(
        frozenset({"heif"}),
        frozenset({"image/heif"}),
        "image",
        frozenset({"heif"}),
    ),
    AttachmentTypeSpec(
        frozenset({"pdf"}),
        frozenset({"application/pdf"}),
        "image",
        frozenset({"pdf"}),
    ),
    AttachmentTypeSpec(
        frozenset({"docx"}),
        frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
        "raw",
        frozenset({"docx"}),
    ),
    AttachmentTypeSpec(
        frozenset({"xlsx"}),
        frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
        "raw",
        frozenset({"xlsx"}),
    ),
    AttachmentTypeSpec(
        frozenset({"txt"}),
        frozenset({"text/plain"}),
        "raw",
        frozenset({"txt"}),
    ),
    AttachmentTypeSpec(
        frozenset({"csv"}),
        frozenset({"text/csv", "text/plain"}),
        "raw",
        frozenset({"csv", "txt"}),
    ),
)

EXTENSION_TO_SPEC: dict[str, AttachmentTypeSpec] = {}
for _spec in ATTACHMENT_TYPE_SPECS:
    for _ext in _spec.extensions:
        EXTENSION_TO_SPEC[_ext] = _spec

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    mime for spec in ATTACHMENT_TYPE_SPECS for mime in spec.mime_types
)


@dataclass(frozen=True)
class NormalizedUploadRequest:
    file_name: str
    mime_type: str
    resource_type: str
    extension: str
    spec: AttachmentTypeSpec


def sanitize_file_name(file_name: str) -> str:
    cleaned = file_name.replace("/", "-").replace("\\", "-")
    cleaned = _FILENAME_UNSAFE.sub("", cleaned)
    cleaned = cleaned.strip().strip(".")
    if not cleaned:
        raise AttachmentValidationError("Invalid file name.")
    return cleaned[:255]


def extract_extension(file_name: str) -> str:
    parts = file_name.rsplit(".", 1)
    if len(parts) < 2 or not parts[1]:
        raise AttachmentValidationError("File name must include a supported extension.")
    ext = parts[1].lower()
    if not ext or ext not in EXTENSION_TO_SPEC:
        raise AttachmentValidationError(f"Unsupported file extension: .{ext or '(none)'}")
    return ext


def normalize_upload_request(payload: AttachmentSignRequest) -> NormalizedUploadRequest:
    if payload.file_size > MAX_FILE_SIZE_BYTES:
        raise AttachmentValidationError(
            f"File too large ({payload.file_size} bytes). Maximum is {MAX_FILE_SIZE_BYTES} bytes."
        )

    sanitized = sanitize_file_name(payload.file_name)
    ext = extract_extension(sanitized)
    spec = EXTENSION_TO_SPEC[ext]

    if payload.mime_type not in spec.mime_types:
        raise AttachmentValidationError(
            f"MIME type {payload.mime_type!r} does not match .{ext} "
            f"(expected one of: {', '.join(sorted(spec.mime_types))})."
        )

    return NormalizedUploadRequest(
        file_name=sanitized,
        mime_type=payload.mime_type,
        resource_type=spec.resource_type,
        extension=ext,
        spec=spec,
    )


def validate_cloudinary_resource(
    *,
    file_name: str,
    resource: dict[str, Any],
) -> None:
    """Ensure Cloudinary metadata matches the signed allowlist for this file name."""
    ext = extract_extension(file_name)
    spec = EXTENSION_TO_SPEC[ext]

    cloud_format = str(resource.get("format") or "").lower()
    cloud_resource_type = str(resource.get("resource_type") or "")

    if cloud_resource_type != spec.resource_type:
        raise AttachmentConfirmError(
            f"Cloudinary resource_type {cloud_resource_type!r} does not match .{ext} "
            f"(expected {spec.resource_type!r})."
        )

    if cloud_format not in spec.confirm_formats:
        raise AttachmentConfirmError(
            f"Cloudinary format {cloud_format!r} is not allowed for .{ext} "
            f"(expected one of: {', '.join(sorted(spec.confirm_formats))})."
        )
