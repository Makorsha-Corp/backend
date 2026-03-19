"""Standard response schemas for API layer"""
from pydantic import BaseModel, Field
from typing import List, Optional, Generic, TypeVar, Any
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Message type enum"""
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ActionMessage(BaseModel):
    """
    Individual action message.

    Used to communicate what happened during a backend operation.
    Multiple messages can be returned to show step-by-step actions.
    """
    type: MessageType = Field(
        description="Type of message (success, info, warning, error)"
    )
    message: str = Field(
        description="Human-readable message"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this action occurred"
    )
    details: Optional[dict] = Field(
        None,
        description="Additional structured data about the action"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "success",
                "message": "Sales order SO-2025-001 created successfully",
                "timestamp": "2025-01-24T10:30:00Z",
                "details": {"order_id": 123}
            }
        }


DataT = TypeVar('DataT')


class ActionResponse(BaseModel, Generic[DataT]):
    """
    Response for complex backend actions.

    Returns data + messages about what happened during the operation.
    Use this when an endpoint performs multiple steps and you want to
    communicate each step to the frontend.
    """
    data: DataT = Field(
        description="The main response data"
    )
    messages: List[ActionMessage] = Field(
        default_factory=list,
        description="List of action messages describing what happened"
    )
    request_id: Optional[str] = Field(
        None,
        description="Unique request identifier for debugging"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "data": {"id": 123, "sales_order_number": "SO-2025-001"},
                "messages": [
                    {
                        "type": "success",
                        "message": "Sales order created",
                        "timestamp": "2025-01-24T10:30:00Z"
                    },
                    {
                        "type": "info",
                        "message": "Inventory reserved for 3 items",
                        "timestamp": "2025-01-24T10:30:01Z"
                    }
                ],
                "request_id": "req_abc123xyz"
            }
        }


# Helper functions to create messages
def success_message(msg: str, details: Optional[dict] = None) -> ActionMessage:
    """Create a success message"""
    return ActionMessage(type=MessageType.SUCCESS, message=msg, details=details)


def info_message(msg: str, details: Optional[dict] = None) -> ActionMessage:
    """Create an info message"""
    return ActionMessage(type=MessageType.INFO, message=msg, details=details)


def warning_message(msg: str, details: Optional[dict] = None) -> ActionMessage:
    """Create a warning message"""
    return ActionMessage(type=MessageType.WARNING, message=msg, details=details)


def error_message(msg: str, details: Optional[dict] = None) -> ActionMessage:
    """Create an error message"""
    return ActionMessage(type=MessageType.ERROR, message=msg, details=details)
