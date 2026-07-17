"""Payment transaction event DAO operations"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.payment_transaction_event import PaymentTransactionEvent


class PaymentTransactionEventDAO(BaseDAO[PaymentTransactionEvent, dict, dict]):
    def get_by_payment_transaction(
        self, db: Session, *, payment_transaction_id: int
    ) -> List[PaymentTransactionEvent]:
        return (
            db.query(PaymentTransactionEvent)
            .filter(PaymentTransactionEvent.payment_transaction_id == payment_transaction_id)
            .order_by(PaymentTransactionEvent.created_at.asc())
            .all()
        )


payment_transaction_event_dao = PaymentTransactionEventDAO(PaymentTransactionEvent)
