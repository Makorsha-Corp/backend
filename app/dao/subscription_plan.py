"""SubscriptionPlan DAO"""

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.subscription_plan import SubscriptionPlanCreate, SubscriptionPlanUpdate


class SubscriptionPlanDAO(BaseDAO[SubscriptionPlan, SubscriptionPlanCreate, SubscriptionPlanUpdate]):
    """DAO for subscription plan operations"""

    def get_by_name(self, db: Session, *, name: str) -> SubscriptionPlan | None:
        """Get subscription plan by name"""
        return db.query(SubscriptionPlan).filter(SubscriptionPlan.name == name).first()

    def get_default_plan(self, db: Session) -> SubscriptionPlan | None:
        """Get the default subscription plan"""
        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_default == True, SubscriptionPlan.is_active == True)
            .first()
        )

subscription_plan_dao = SubscriptionPlanDAO(SubscriptionPlan)
