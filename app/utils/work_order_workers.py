"""Resolve free-text worker names to workspace members."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao


_NAME_SPLIT = re.compile(r"[,;]+")


def parse_worker_names(text: str | None) -> list[str]:
    if not text or not text.strip():
        return []
    return [part.strip() for part in _NAME_SPLIT.split(text) if part.strip()]


def join_worker_names(names: Sequence[str]) -> str:
    return ", ".join(name.strip() for name in names if name and name.strip())


@dataclass(frozen=True)
class MemberLookup:
    user_id: int
    name: str | None
    email: str | None


@dataclass(frozen=True)
class WorkerNameResolution:
    matched_user_ids: list[int]
    unmatched_names: list[str]
    display_text: str


def _normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


def resolve_names_to_members(
    names: Iterable[str],
    members: Sequence[MemberLookup],
) -> WorkerNameResolution:
    active = list(members)
    matched_ids: list[int] = []
    unmatched: list[str] = []
    display_names: list[str] = []

    for raw in names:
        token = raw.strip()
        if not token:
            continue
        norm = _normalize(token)
        hit: MemberLookup | None = None
        for member in active:
            if _normalize(member.name) == norm or _normalize(member.email) == norm:
                hit = member
                break
        if hit is not None:
            if hit.user_id not in matched_ids:
                matched_ids.append(hit.user_id)
            display_names.append((hit.name or hit.email or token).strip())
        else:
            unmatched.append(token)
            display_names.append(token)

    return WorkerNameResolution(
        matched_user_ids=matched_ids,
        unmatched_names=unmatched,
        display_text=join_worker_names(display_names),
    )


def resolve_worker_text_to_members(
    text: str | None,
    members: Sequence[MemberLookup],
) -> WorkerNameResolution:
    return resolve_names_to_members(parse_worker_names(text), members)


def load_active_member_lookups(session: Session, workspace_id: int) -> list[MemberLookup]:
    rows = workspace_member_dao.get_workspace_members(session, workspace_id=workspace_id, status="active")
    lookups: list[MemberLookup] = []
    for row in rows:
        profile = profile_dao.get(session, id=row.user_id)
        lookups.append(
            MemberLookup(
                user_id=row.user_id,
                name=profile.name if profile else None,
                email=profile.email if profile else None,
            )
        )
    return lookups


def display_names_for_user_ids(session: Session, user_ids: Sequence[int]) -> str:
    names: list[str] = []
    for user_id in user_ids:
        profile = profile_dao.get(session, id=user_id)
        if profile and profile.name:
            names.append(profile.name)
        elif profile and profile.email:
            names.append(profile.email)
        else:
            names.append(f"User #{user_id}")
    return join_worker_names(names)
