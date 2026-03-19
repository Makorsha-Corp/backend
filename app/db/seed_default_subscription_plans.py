"""
Seed default subscription plans at app startup

This module provides functionality to create default subscription plans
when the database is first initialized. Unlike workspace-scoped seeds,
subscription plans are global (not per-workspace).
"""
from sqlalchemy.orm import Session
from app.models.subscription_plan import SubscriptionPlan


DEFAULT_PLANS = [
    {
        "name": "free",
        "display_name": "Free Plan",
        "description": "Perfect for getting started",
        "price_monthly": None,
        "price_yearly": None,
        "currency": "USD",
        "max_members": 3,
        "max_storage_mb": 1000,
        "max_orders_per_month": 50,
        "max_factories": 1,
        "max_machines": 5,
        "max_projects": 3,
        "features": ["basic_inventory", "basic_orders"],
        "is_default": True,
        "is_active": True,
    },
    {
        "name": "pro",
        "display_name": "Pro Plan",
        "description": "For growing businesses",
        "price_monthly": 99.00,
        "price_yearly": 990.00,
        "currency": "USD",
        "max_members": 10,
        "max_storage_mb": 10000,
        "max_orders_per_month": 500,
        "max_factories": 3,
        "max_machines": 25,
        "max_projects": 15,
        "features": ["advanced_inventory", "advanced_orders", "analytics", "api_access"],
        "is_default": False,
        "is_active": True,
    },
    {
        "name": "enterprise",
        "display_name": "Enterprise Plan",
        "description": "For large organizations",
        "price_monthly": 299.00,
        "price_yearly": 2990.00,
        "currency": "USD",
        "max_members": -1,
        "max_storage_mb": -1,
        "max_orders_per_month": -1,
        "max_factories": -1,
        "max_machines": -1,
        "max_projects": -1,
        "features": ["all_features", "sso", "custom_integration", "dedicated_support"],
        "is_default": False,
        "is_active": True,
    },
]


def seed_default_subscription_plans(db: Session) -> list[SubscriptionPlan]:
    """
    Seed default subscription plans (global, not per-workspace).

    This is idempotent - it checks by name before creating.
    Called at app startup from init_db().

    Args:
        db: Database session

    Returns:
        List of created SubscriptionPlan objects

    Note:
        This function commits the transaction since it runs at startup
        outside of any request context.
    """
    created_plans = []

    for plan_data in DEFAULT_PLANS:
        existing = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.name == plan_data["name"])
            .first()
        )

        if not existing:
            plan = SubscriptionPlan(**plan_data)
            db.add(plan)
            created_plans.append(plan)

    if created_plans:
        db.flush()

    return created_plans
