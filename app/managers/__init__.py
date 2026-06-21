"""
Managers module for business logic layer

HYBRID PATTERN:
- Utility Managers: Cross-cutting operations (Inventory transfers)
- Standalone Managers: Simple entities (Part catalog)
"""
from app.managers.base_manager import BaseManager
from app.managers.inventory_manager import inventory_manager, InventoryManager
from app.managers.item_manager import item_manager, ItemManager

__all__ = [
    "BaseManager",
    "InventoryManager",
    "inventory_manager",
    "ItemManager",
    "item_manager",
]
