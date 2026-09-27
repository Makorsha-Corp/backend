"""
Managers module for business logic layer

HYBRID PATTERN:
- Utility Managers: Cross-cutting operations (Inventory transfers)
- Standalone Managers: Simple entities (Part catalog)
"""
from app.managers.base_manager import BaseManager
from app.managers.inventory_manager import InventoryManager, inventory_manager
from app.managers.item_manager import ItemManager, item_manager

__all__ = [
    "BaseManager",
    "InventoryManager",
    "ItemManager",
    "inventory_manager",
    "item_manager",
]
