"""Unit tests for app/core/notification_types.py.

Implements tests/unit/core/notification_types.cases.md, one test per case, in
card order. Plain value assertions; no database. Nothing is mocked
(Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
import re

from app.core import notification_types as nt

# Convention "KINDS"
KINDS = [nt.APPROVAL_ASSIGNED, nt.APPROVAL_PENDING, nt.SECTION_CONFIRM, nt.INVOICE_ACTION, nt.MENTION]

# Convention "SOURCES"
SOURCES = [nt.SOURCE_APPROVER, nt.SOURCE_ORDER, nt.SOURCE_SECTION, nt.SOURCE_INVOICE, nt.SOURCE_DISCUSSION]

# Convention "WEB_KINDS": the web app's NotificationKind list, copied from the spec's Notes
WEB_KINDS = {
    "approval_pending", "approval_assigned", "section_confirm", "invoice_action", "low_stock",
    "project_update", "maintenance", "system", "mention",
}


# --------------------------------------------------------------------------- #
# Notification kinds
# --------------------------------------------------------------------------- #


# [claude] NTY-K-01
def test_nty_k_01__the_five_kind_values_are_exactly_as_specified():
    """NTY-K-01 — the five kind values are exactly as specified.
    Rules: kinds R1"""
    values = KINDS  # noqa: F841  (the card's When; its Then lines read the constants by name)

    # Then 1
    assert nt.APPROVAL_ASSIGNED == "approval_assigned"
    # Then 2
    assert nt.APPROVAL_PENDING == "approval_pending"
    # Then 3
    assert nt.SECTION_CONFIRM == "section_confirm"
    # Then 4
    assert nt.INVOICE_ACTION == "invoice_action"
    # Then 5
    assert nt.MENTION == "mention"


# [claude] NTY-K-02
def test_nty_k_02__every_kind_is_one_the_web_app_knows_and_the_five_are_pairwise_different():
    """NTY-K-02 — every kind is one the web app knows, and the five are pairwise different.
    Rules: kinds R2"""
    values = KINDS

    # Then 1
    assert [v for v in values if v not in WEB_KINDS] == []
    # Then 2
    assert len(set(values)) == 5


# [claude] NTY-K-03
def test_nty_k_03__every_kind_fits_30_characters_and_uses_lower_case_ascii_letters_and_only():
    """NTY-K-03 — every kind fits 30 characters and uses lower-case ASCII letters and "_" only.
    Rules: kinds R3"""
    values = KINDS

    # Then 1
    assert [v for v in values if len(v) > 30] == []
    # Then 2
    assert [v for v in values if not re.fullmatch(r"[a-z_]+", v)] == []


# --------------------------------------------------------------------------- #
# Source kinds
# --------------------------------------------------------------------------- #


# [claude] NTY-S-01
def test_nty_s_01__the_five_source_values_are_exactly_as_specified_and_pairwise_different():
    """NTY-S-01 — the five source values are exactly as specified and pairwise different.
    Rules: sources R4"""
    values = SOURCES

    # Then 1
    assert nt.SOURCE_APPROVER == "approver"
    # Then 2
    assert nt.SOURCE_ORDER == "order"
    # Then 3
    assert nt.SOURCE_SECTION == "section"
    # Then 4
    assert nt.SOURCE_INVOICE == "invoice"
    # Then 5
    assert nt.SOURCE_DISCUSSION == "discussion"
    # Then 6
    assert len(set(values)) == 5


# [claude] NTY-S-02
def test_nty_s_02__every_source_fits_30_characters_and_uses_lower_case_ascii_letters_only():
    """NTY-S-02 — every source fits 30 characters and uses lower-case ASCII letters only.
    Rules: sources R5"""
    values = SOURCES

    # Then 1
    assert [v for v in values if len(v) > 30] == []
    # Then 2
    assert [v for v in values if not re.fullmatch(r"[a-z]+", v)] == []
