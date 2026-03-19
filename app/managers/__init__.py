"""
Managers module for business logic layer

HYBRID PATTERN:
- Aggregate Managers: Entity + children (Order + Parts + Status)
- Utility Managers: Cross-cutting operations (Inventory transfers)
- Standalone Managers: Simple entities (Part catalog)
"""
from app.managers.base_manager import BaseManager

# ============================================================================
# AGGREGATE MANAGERS (Entity + Children)
# ============================================================================
from app.managers.order_manager import order_manager, OrderManager

# ============================================================================
# UTILITY MANAGERS (Cross-Cutting Operations)
# ============================================================================
from app.managers.inventory_manager import inventory_manager, InventoryManager

# ============================================================================
# STANDALONE MANAGERS (Independent Entities)
# ============================================================================
from app.managers.item_manager import item_manager, ItemManager

__all__ = [
    # Base
    "BaseManager",

    # Aggregate Managers
    "OrderManager",
    "order_manager",

    # Utility Managers
    "InventoryManager",
    "inventory_manager",

    # Standalone Managers
    "ItemManager",
    "item_manager",
]
