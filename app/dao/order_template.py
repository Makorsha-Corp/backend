"""Order template DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.order_template import OrderTemplate
from app.models.order_template_item import OrderTemplateItem
from app.schemas.order_template import OrderTemplateCreate, OrderTemplateUpdate, OrderTemplateItemCreate, OrderTemplateItemUpdate


class OrderTemplateDAO(BaseDAO[OrderTemplate, OrderTemplateCreate, OrderTemplateUpdate]):
    def get_by_workspace(self, db: Session, *, workspace_id: int, is_active: Optional[bool] = None, expense_category: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[OrderTemplate]:
        query = db.query(OrderTemplate).filter(OrderTemplate.workspace_id == workspace_id)
        if is_active is not None:
            query = query.filter(OrderTemplate.is_active == is_active)
        if expense_category:
            query = query.filter(OrderTemplate.expense_category == expense_category)
        return query.order_by(desc(OrderTemplate.created_at)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[OrderTemplate]:
        return db.query(OrderTemplate).filter(OrderTemplate.id == id, OrderTemplate.workspace_id == workspace_id).first()


class OrderTemplateItemDAO(BaseDAO[OrderTemplateItem, OrderTemplateItemCreate, OrderTemplateItemUpdate]):
    def get_by_template(self, db: Session, *, order_template_id: int, workspace_id: int) -> List[OrderTemplateItem]:
        return db.query(OrderTemplateItem).filter(OrderTemplateItem.order_template_id == order_template_id, OrderTemplateItem.workspace_id == workspace_id).order_by(OrderTemplateItem.line_number).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[OrderTemplateItem]:
        return db.query(OrderTemplateItem).filter(OrderTemplateItem.id == id, OrderTemplateItem.workspace_id == workspace_id).first()


order_template_dao = OrderTemplateDAO(OrderTemplate)
order_template_item_dao = OrderTemplateItemDAO(OrderTemplateItem)
