"""Normalize item names for duplicate / similar-name detection."""
from __future__ import annotations

import re

MIN_SIMILAR_NAME_LENGTH = 3
SIMILARITY_THRESHOLD = 0.35

# Glue a number to a short trailing unit token: "22 m" -> "22m"
_UNIT_GLUE_PATTERN = re.compile(r"(\d+)\s+([a-z]{1,4})\b")


def normalize_item_name(name: str) -> str:
    """
    Normalize an item name for comparison.

    Steps: lowercase, trim, collapse whitespace, glue digit+unit,
    replace punctuation with spaces, final whitespace collapse.
    """
    if not name:
        return ""

    normalized = name.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = _UNIT_GLUE_PATTERN.sub(r"\1\2", normalized)
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
