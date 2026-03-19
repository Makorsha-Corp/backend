"""
Audit logging utility for financial operations.

Provides a simple interface for logging audit events across the financial system.
"""
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.dao.financial_audit_log import financial_audit_log_dao, FinancialAuditLogCreate


def log_financial_audit(
    session: Session,
    *,
    workspace_id: int,
    entity_type: str,
    entity_id: int,
    action_type: str,
    performed_by: int,
    changes: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """
    Log a financial audit event.

    Args:
        session: Database session
        workspace_id: Workspace ID
        entity_type: Type of entity ('account', 'invoice', 'payment')
        entity_id: Entity ID
        action_type: Action performed ('created', 'updated', 'deleted', etc.)
        performed_by: User ID who performed the action
        changes: Dict with before/after changes (optional)
        description: Human-readable description (optional)
        related_entity_type: Related entity type (optional, e.g., 'invoice' for a payment)
        related_entity_id: Related entity ID (optional)
        ip_address: IP address of user (optional)
        user_agent: User agent string (optional)

    Example:
        # Log account creation
        log_financial_audit(
            session=db,
            workspace_id=1,
            entity_type='account',
            entity_id=5,
            action_type='created',
            performed_by=user_id,
            changes={'after': {'name': 'ABC Suppliers', 'email': 'contact@abc.com'}},
            description="Account 'ABC Suppliers' created"
        )

        # Log invoice creation
        log_financial_audit(
            session=db,
            workspace_id=1,
            entity_type='invoice',
            entity_id=10,
            action_type='created',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=5,
            changes={'after': {'invoice_type': 'payable', 'amount': 5000.00}},
            description="Payable invoice created for account 'ABC Suppliers'"
        )

        # Log payment with invoice status change
        log_financial_audit(
            session=db,
            workspace_id=1,
            entity_type='payment',
            entity_id=15,
            action_type='created',
            performed_by=user_id,
            related_entity_type='invoice',
            related_entity_id=10,
            changes={
                'after': {'payment_amount': 2000.00},
                'invoice_status_changed': {'before': 'unpaid', 'after': 'partial'}
            },
            description="Payment of $2000.00 recorded, invoice status changed to partial"
        )
    """
    audit_data = FinancialAuditLogCreate(
        entity_type=entity_type,
        entity_id=entity_id,
        action_type=action_type,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        changes=changes,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent
    )

    log_dict = audit_data.model_dump()
    log_dict['workspace_id'] = workspace_id
    log_dict['performed_by'] = performed_by

    financial_audit_log_dao.create(session, obj_in=log_dict)


def create_change_dict(before: Optional[Dict[str, Any]] = None, after: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Helper to create a changes dict with before/after values.

    Args:
        before: Dict of values before the change
        after: Dict of values after the change

    Returns:
        Dict with 'before' and 'after' keys

    Example:
        changes = create_change_dict(
            before={'status': 'unpaid'},
            after={'status': 'paid'}
        )
    """
    result = {}
    if before is not None:
        result['before'] = before
    if after is not None:
        result['after'] = after
    return result


def extract_relevant_fields(obj: Any, fields: list) -> Dict[str, Any]:
    """
    Extract specific fields from an object for audit logging.

    Converts non-JSON-serializable types (Decimal, datetime, date) to JSON-compatible formats.

    Args:
        obj: Object to extract fields from
        fields: List of field names to extract

    Returns:
        Dict with field names and JSON-serializable values

    Example:
        account_data = extract_relevant_fields(account, ['name', 'email', 'phone'])
        # Returns: {'name': 'ABC Suppliers', 'email': 'contact@abc.com', 'phone': '+123...'}
    """
    result = {}
    for field in fields:
        if hasattr(obj, field):
            value = getattr(obj, field)

            # Convert non-JSON-serializable types to JSON-compatible formats
            # NOTE: Check Decimal and datetime/date BEFORE other types
            if isinstance(value, Decimal):
                # Convert Decimal to float
                result[field] = float(value)
            elif isinstance(value, datetime):
                # Convert datetime to ISO string (must check before date!)
                result[field] = value.isoformat()
            elif isinstance(value, date):
                # Convert date to ISO string
                result[field] = value.isoformat()
            elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool)):
                # Skip complex objects (relationships, etc.) but keep primitives
                continue
            else:
                # Keep primitives as-is (str, int, float, bool, None)
                result[field] = value
    return result
