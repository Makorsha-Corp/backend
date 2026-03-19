"""DAO operations"""
from app.dao.base import BaseDAO
from app.models.status import Status
from app.schemas.status import StatusCreate, StatusUpdate


class DAOStatus(BaseDAO[Status, StatusCreate, StatusUpdate]):
    """DAO operations for Status model"""
    pass


status_dao = DAOStatus(Status)
