"""Merge helpers for profile.help_guides_seen JSON."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

MAX_TOUR_IDS_PER_WORKSPACE = 200
TOUR_ID_MAX_LENGTH = 80


def normalize_help_guides_seen(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"by_workspace": {}}
    by_ws = raw.get("by_workspace")
    if not isinstance(by_ws, dict):
        return {"by_workspace": {}}
    cleaned: dict[str, list[str]] = {}
    for key, value in by_ws.items():
        ws_key = str(key)
        if not isinstance(value, list):
            continue
        ids = [str(item) for item in value if isinstance(item, str) and item.strip()]
        cleaned[ws_key] = ids[:MAX_TOUR_IDS_PER_WORKSPACE]
    return {"by_workspace": cleaned}


def has_seen_tour(seen: Any, *, workspace_id: int, tour_id: str) -> bool:
    normalized = normalize_help_guides_seen(seen)
    ids = normalized["by_workspace"].get(str(workspace_id), [])
    return tour_id in ids


def append_seen_tour(seen: Any, *, workspace_id: int, tour_id: str) -> dict[str, Any]:
    normalized = normalize_help_guides_seen(seen)
    ws_key = str(workspace_id)
    current = list(normalized["by_workspace"].get(ws_key, []))
    if tour_id in current:
        return normalized
    current.append(tour_id)
    if len(current) > MAX_TOUR_IDS_PER_WORKSPACE:
        current = current[-MAX_TOUR_IDS_PER_WORKSPACE :]
    out = deepcopy(normalized)
    out["by_workspace"][ws_key] = current
    return out


def remove_seen_tours(
    seen: Any,
    *,
    workspace_id: int,
    tour_ids: list[str],
) -> dict[str, Any]:
    normalized = normalize_help_guides_seen(seen)
    ws_key = str(workspace_id)
    current = list(normalized["by_workspace"].get(ws_key, []))
    remove = set(tour_ids)
    filtered = [tid for tid in current if tid not in remove]
    out = deepcopy(normalized)
    if filtered:
        out["by_workspace"][ws_key] = filtered
    else:
        out["by_workspace"].pop(ws_key, None)
    return out


def reset_seen_tours(seen: Any, *, workspace_id: int | None, scope: str) -> dict[str, Any]:
    normalized = normalize_help_guides_seen(seen)
    if scope == "all":
        return {"by_workspace": {}}
    if scope != "workspace" or workspace_id is None:
        return normalized
    out = deepcopy(normalized)
    out["by_workspace"].pop(str(workspace_id), None)
    return out


def validate_tour_id(tour_id: str) -> str:
    trimmed = tour_id.strip()
    if not trimmed or len(trimmed) > TOUR_ID_MAX_LENGTH:
        raise ValueError("Invalid tour_id")
    for ch in trimmed:
        if ch.isalnum() or ch in "-_":
            continue
        raise ValueError("Invalid tour_id")
    return trimmed
