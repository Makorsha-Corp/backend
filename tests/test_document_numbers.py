"""Workspace document numbers start at 001 and ignore other workspaces' sequences."""
from app.utils.document_numbers import next_document_number


def test_empty_workspace_starts_at_001() -> None:
    assert next_document_number([], "PO-2026-") == "PO-2026-001"
    assert next_document_number([], "SO-2026-") == "SO-2026-001"


def test_next_number_uses_max_suffix_not_count() -> None:
    existing = ["PO-2026-001", "PO-2026-003"]
    assert next_document_number(existing, "PO-2026-") == "PO-2026-004"


def test_other_workspace_numbers_are_not_in_the_list() -> None:
    # Caller must pass only this workspace's numbers. A global unique used to
    # skip 001/002 taken elsewhere and hand a fresh workspace PO-2026-003.
    assert next_document_number([], "PO-2026-") == "PO-2026-001"
