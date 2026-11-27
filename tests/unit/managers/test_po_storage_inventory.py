"""Unit tests for app/managers/po_storage_inventory.py.

Implements tests/unit/managers/po_storage_inventory.cases.md (revision at
source commit e48a092), one test per case. No database session and no mocks:
the module has a single reachable member, the constant
`PO_INVENTORY_SOURCE_TYPE` (spec: "Externals to mock: none").
"""
from app.managers.po_storage_inventory import PO_INVENTORY_SOURCE_TYPE


def test_posi_k_01__constant_value_and_type():
    """POSI-K-01 -- PO_INVENTORY_SOURCE_TYPE == 'purchase_order' and is exactly str.
    Rules: PO_INVENTORY_SOURCE_TYPE R1."""
    assert PO_INVENTORY_SOURCE_TYPE == "purchase_order"
    assert type(PO_INVENTORY_SOURCE_TYPE) is str
