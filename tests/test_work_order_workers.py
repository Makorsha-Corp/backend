"""Tests for work order worker name resolution."""
from app.utils.work_order_workers import (
    MemberLookup,
    parse_worker_names,
    resolve_names_to_members,
    resolve_worker_text_to_members,
)


def test_parse_worker_names_splits_commas_and_semicolons() -> None:
    assert parse_worker_names('Ali, Rahim; Karim') == ['Ali', 'Rahim', 'Karim']


def test_resolve_names_to_members_matches_name_and_email() -> None:
    members = [
        MemberLookup(user_id=1, name='Shohan Chowdhury', email='ceo@example.com'),
        MemberLookup(user_id=2, name='Jane Worker', email='jane@example.com'),
    ]
    result = resolve_names_to_members(['Shohan Chowdhury', 'Unknown Person'], members)
    assert result.matched_user_ids == [1]
    assert result.unmatched_names == ['Unknown Person']
    assert 'Shohan Chowdhury' in result.display_text
    assert 'Unknown Person' in result.display_text


def test_resolve_worker_text_to_members() -> None:
    members = [MemberLookup(user_id=2, name='Jane Worker', email=None)]
    result = resolve_worker_text_to_members('Jane Worker, Bob', members)
    assert result.matched_user_ids == [2]
    assert result.unmatched_names == ['Bob']
