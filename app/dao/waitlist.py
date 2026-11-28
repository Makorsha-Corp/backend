"""DAO for platform waitlist signups."""

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.waitlist_signup import WaitlistSignup
from app.schemas.waitlist import WaitlistSignupRequest


class WaitlistDAO(BaseDAO[WaitlistSignup, WaitlistSignupRequest, WaitlistSignupRequest]):
    _ILIKE_ESCAPE = "\\"

    @staticmethod
    def _escape_ilike(value: str) -> str:
        """Escape user input so %, _ and the escape character match literally."""
        escaped = value.replace("\\", "\\\\")
        escaped = escaped.replace("%", "\\%").replace("_", "\\_")
        return escaped

    def get_by_email(self, db: Session, *, email: str) -> WaitlistSignup | None:
        return db.query(self.model).filter(self.model.email == email).first()

    def list_signups(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        wants_product_updates: bool | None = None,
        status: str | None = None,
    ) -> tuple[list[WaitlistSignup], int]:
        query = db.query(self.model)
        if search:
            term = f"%{self._escape_ilike(search.strip().lower())}%"
            query = query.filter(
                self.model.email.ilike(term, escape=self._ILIKE_ESCAPE)
            )
        if wants_product_updates is not None:
            query = query.filter(self.model.wants_product_updates == wants_product_updates)
        if status is not None:
            query = query.filter(self.model.status == status)

        total = query.count()
        items = (
            query.order_by(self.model.created_at.desc(), self.model.id.desc())
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
        company_name: str | None,
        wants_product_updates: bool,
        source: str | None,
        ip_hash: str | None,
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
