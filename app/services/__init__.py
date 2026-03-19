"""
Services module for business orchestration

RESPONSIBILITIES:
1. Multi-aggregate coordination (OrderManager + InventoryManager)
2. Complex workflows (STM, STP, MTM orders)
3. Transaction management (commit/rollback)
4. Cross-cutting concerns (email, notifications, audit)
5. External integrations (future: supplier APIs, payment gateways)
6. Authorization & feature flags

Services orchestrate managers - they don't implement business logic.
"""
from app.services.base_service import BaseService
from app.services.order_service import order_service, OrderService
from app.services.item_service import item_service, ItemService

__all__ = [
    "BaseService",
    "OrderService",
    "order_service",
    "ItemService",
    "item_service",
]
