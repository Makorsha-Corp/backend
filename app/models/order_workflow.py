"""Order workflow model"""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.types import TypeDecorator, Text
import json
from app.db.base_class import Base


class JSONEncodedList(TypeDecorator):
    """Represents an immutable structure as a JSON-encoded list."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class OrderWorkflow(Base):
    """Order workflow model"""

    __tablename__ = "order_workflows"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    status_sequence = Column(JSONEncodedList, nullable=False)
    allowed_reverts_json = Column(JSON, nullable=True)
