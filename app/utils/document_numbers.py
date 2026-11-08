"""Next document number inside one workspace. Numbers may repeat across workspaces."""
from __future__ import annotations

from collections.abc import Iterable


def next_document_number(existing: Iterable[str], prefix: str) -> str:
    """Highest suffix for `prefix` plus one, zero-padded to 3 digits.

    `PO-2026-002` and `PO-2026-010` yield `PO-2026-011`. A gap does not reuse
    a lower number, so a deleted `001` does not collide with a later insert.
    """
    max_seq = 0
    for num in existing:
        tail = str(num).rsplit("-", 1)[-1]
        try:
            seq = int(tail)
        except ValueError:
            continue
        if seq > max_seq:
            max_seq = seq
    return f"{prefix}{max_seq + 1:03d}"
