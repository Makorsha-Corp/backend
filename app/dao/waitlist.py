"""DAO for platform waitlist signups."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.waitlist_signup import WaitlistSignup
from app.schemas.waitlist import WaitlistSignupRequest


class WaitlistDAO(BaseDAO[WaitlistSignup, WaitlistSignupRequest, WaitlistSignupRequest]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[WaitlistSignup]:
        return db.query(self.model).filter(self.model.email == email).first()

    def list_signups(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        wants_product_updates: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[WaitlistSignup], int]:
        query = db.query(self.model)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(self.model.email.ilike(term))
        if wants_product_updates is not None:
            query = query.filter(self.model.wants_product_updates == wants_product_updates)
        if status is not None:
            query = query.filter(self.model.status == status)

        total = query.count()
        items = (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def create_signup(
        self,
        db: Session,
        *,
        email: str,
        first_name: str,
        last_name: str,
        company_name: Optional[str],
        wants_product_updates: bool,
        source: Optional[str],
        ip_hash: Optional[str],
    ) -> WaitlistSignup:
        db_obj = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            wants_product_updates=wants_product_updates,
            source=source,
            ip_hash=ip_hash,
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def update_status(
        self, db: Session, *, signup: WaitlistSignup, status: str
    ) -> WaitlistSignup:
        signup.status = status
        db.add(signup)
        db.flush()
        return signup


waitlist_dao = WaitlistDAO(WaitlistSignup)
