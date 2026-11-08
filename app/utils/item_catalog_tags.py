"""Map production BOM roles to catalog item tag codes."""
from __future__ import annotations

from typing import Optional

PRODUCTION_ROLE_TAG_CODES: dict[str, str] = {
    "input": "raw_material",
    "output": "finished_good",
    "waste": "waste",
    "byproduct": "byproduct",
}


def catalog_tag_code_for_production_role(item_role: str) -> Optional[str]:
    return PRODUCTION_ROLE_TAG_CODES.get(item_role)
