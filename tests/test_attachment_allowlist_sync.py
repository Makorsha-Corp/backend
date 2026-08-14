"""Guard: backend allowlist stays aligned with frontend attachmentAllowlist.ts mirror.

When changing allowed types, update:
- backend/app/utils/attachment_allowlist.py
- frontend/src/lib/attachmentAllowlist.ts
- EXPECTED_EXTENSION_SPECS below
"""
from app.core.config import settings
from app.utils.attachment_allowlist import (
    EXTENSION_TO_SPEC,
    MAX_FILE_SIZE_BYTES,
)

# Frozen checklist — must match frontend ATTACHMENT_EXTENSION_SPECS + MAX_ATTACHMENT_BYTES.
EXPECTED_EXTENSION_SPECS: dict[str, frozenset[str]] = {
    "jpg": frozenset({"image/jpeg"}),
    "jpeg": frozenset({"image/jpeg"}),
    "png": frozenset({"image/png"}),
    "webp": frozenset({"image/webp"}),
    "heic": frozenset({"image/heic"}),
    "heif": frozenset({"image/heif"}),
    "pdf": frozenset({"application/pdf"}),
    "docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
    "xlsx": frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
    "txt": frozenset({"text/plain"}),
    "csv": frozenset({"text/csv", "text/plain"}),
}

EXPECTED_MAX_BYTES = 10 * 1024 * 1024
EXPECTED_MAX_ATTACHMENTS_PER_ENTITY = 25


def test_extension_keys_match_frontend_mirror() -> None:
    assert set(EXTENSION_TO_SPEC.keys()) == set(EXPECTED_EXTENSION_SPECS.keys())


def test_mime_types_match_frontend_mirror() -> None:
    for ext, expected_mimes in EXPECTED_EXTENSION_SPECS.items():
        spec = EXTENSION_TO_SPEC[ext]
        assert frozenset(spec.mime_types) == expected_mimes, (
            f".{ext}: backend {set(spec.mime_types)} != expected {set(expected_mimes)}"
        )


def test_max_file_size_matches_frontend() -> None:
    assert MAX_FILE_SIZE_BYTES == EXPECTED_MAX_BYTES


def test_max_attachments_per_entity_matches_frontend() -> None:
    assert settings.MAX_ATTACHMENTS_PER_ENTITY == EXPECTED_MAX_ATTACHMENTS_PER_ENTITY
